import os
import sys
# os.environ['MKL_NUM_THREADS'] = '8'
from data_functions import *
from util import *
import numpy as np

np.seterr(divide='ignore')  # Repress Invalid value or division by zero error
from numpy.matlib import repmat, sin, cos
import hdf5storage


def calc_CF_solar(hour, reg, param, merraData, rasterData, calc_type):
    Ind = param["Ind"]
    Crd = param["Crd"]
    res = param["res"]
    pv = param["PV"]["technical"]
    if calc_type == 'Surface':
        m = param["m"]
        n = param["n"]

        # Load MERRA data, increase its resolution, and fit it to the extent
        CLEARNESS_h = merraData["CLEARNESS"][:, :, hour]
        CLEARNESS_h = resizem(CLEARNESS_h, m[1, reg], n[1, reg])
        TEMP_h = merraData["T2M"][:, :, hour]
        TEMP_h = resizem(TEMP_h, m[1, reg], n[1, reg]) - 273.15  # Convert to Celsius
        # Compute the angles
        A_phi, A_omega, A_delta, A_alpha, A_beta, A_azimuth, A_orientation, sunrise, sunset = \
            angles(hour, reg, Crd[reg, :], m[1, reg], n[1, reg], res)
        # Other matrices
        A_albedo = rasterData["A_albedo"]
        A_Ross = rasterData["A_Ross"]
    elif calc_type == 'Points':
        Crd_Locations = param["Crd_Locations"]
        Ind_Locations = param["Ind_Locations"]
        # Load MERRA2 data for the desired points
        CLEARNESS_h = merraData["CLEARNESS"][:, :, hour]
        CLEARNESS_h = CLEARNESS_h[
            np.ix_(np.squeeze(Ind_Locations[0, reg, :, 0]) - 1, np.squeeze(Ind_Locations[0, reg, :, 1]) - 1)]
        CLEARNESS_h = np.diagonal(CLEARNESS_h)
        TEMP_h = merraData["T2M"][:, :, hour]
        TEMP_h = TEMP_h[np.ix_(np.squeeze(Ind_Locations[0, reg, :, 0]) - 1,
                               np.squeeze(Ind_Locations[0, reg, :, 1]) - 1)] - 273.15  # Convert to Celsius
        TEMP_h = np.diagonal(TEMP_h)
        # Compute the angles
        A_phi, A_omega, A_delta, A_alpha, A_beta, A_azimuth, A_orientation, sunrise, sunset = angles(hour, np.squeeze(
            Crd_Locations[reg, :, :]))
        # Other vectors
        A_albedo = rasterData["A_albedo"][
            np.ix_(np.squeeze(Ind_Locations[0, reg, :, 0]) - 1, np.squeeze(Ind_Locations[0, reg, :, 1]) - 1)]
        A_albedo = np.diagonal(A_albedo)
        A_Ross = rasterData["A_Ross"][
            np.ix_(np.squeeze(Ind_Locations[0, reg, :, 0]) - 1, np.squeeze(Ind_Locations[0, reg, :, 1]) - 1)]
        A_Ross = np.diagonal(A_Ross)

    if pv["tracking"] == 1:
        A_beta = 90 - A_alpha
    elif pv["tracking"] == 2:
        A_beta = 90 - A_alpha
        A_orientation = A_azimuth

    aux = np.maximum(np.minimum((sind(A_delta) * sind(A_phi) * cosd(A_beta)
                                 - sind(A_delta) * cosd(A_phi) * sind(A_beta) * cosd(A_orientation) + cosd(
                A_delta) * cosd(A_phi) * cosd(A_beta)
                                 * cosd(A_omega) + cosd(A_delta) * sind(A_phi) * sind(A_beta) * cosd(A_orientation)
                                 * cosd(A_omega) + cosd(A_delta) * sind(A_beta) * sind(A_orientation) * sind(A_omega)),
                                1), -1)
    A_incidence = arccosd(aux)

    # Compute the hourly TOA radiation
    TOA_h = toa_hourly(A_alpha, hour)

    # Compute the ratio of diffuse radiation
    RATIO = global2diff(CLEARNESS_h, A_alpha.shape)

    # Compute the coefficients for the HDKR model
    R_b = cosd(A_incidence) / sind(A_alpha)
    A_i = (1 - RATIO) * CLEARNESS_h
    f = (1 - RATIO) ** 0.5

    F_direct, F_diffuse, F_reflected = coefficients(A_beta, RATIO, R_b, A_i, f, hour, sunrise, sunset)

    # Compute the shading losses
    # The following line requires long computation time, replace with SHADING = 0 for fast computation
    SHADING = 0

    F = F_diffuse + F_direct * (1 - SHADING) + F_reflected * A_albedo
    F[F > 1] = 1

    # Compute the incident radiation
    GHI_h = TOA_h * CLEARNESS_h
    GHI_h[GHI_h < 0] = 0
    GHI_h[np.isnan(GHI_h)] = 0
    G_tilt_h = GHI_h * F

    # Compute losses due to heating of the PV cells
    LOSS_TEMP = loss(G_tilt_h, TEMP_h, A_Ross, pv)

    # Compute the hourly capacity factor
    CF_pv = ((A_alpha > 0) * 1) * G_tilt_h / 1000 * (1 - LOSS_TEMP)
    CF_pv[CF_pv > 1] = 1

    # For CSP: tracking like pv.tracking = 1
    A_beta = 90 - A_alpha
    aux = np.maximum(np.minimum((sind(A_delta) * sind(A_phi) * cosd(A_beta)
                                 - sind(A_delta) * cosd(A_phi) * sind(A_beta) * cosd(A_orientation) + cosd(
                A_delta) * cosd(A_phi) * cosd(A_beta)
                                 * cosd(A_omega) + cosd(A_delta) * sind(A_phi) * sind(A_beta) * cosd(A_orientation)
                                 * cosd(A_omega) + cosd(A_delta) * sind(A_beta) * sind(A_orientation) * sind(A_omega)),
                                1), -1)
    A_incidence = arccosd(aux)
    R_b = cosd(A_incidence) / sind(A_alpha)
    F_direct_csp, _, _ = coefficients(90 - A_alpha, RATIO, R_b, A_i, f, hour, sunrise, sunset)
    CF_csp = TOA_h * CLEARNESS_h * F_direct_csp * (1 - SHADING)
    CF_csp[CF_csp > 1] = 1
    return CF_pv, CF_csp


def calc_FLH_solar(hours, args):
    # Decomposing the tuple args
    reg = args[0]
    paths = args[1]
    param = args[2]
    nRegions = args[3]
    region_name = args[4]
    rasterData = args[5]
    tech = args[6]

    Ind = param["Ind"]
    regions_shp = param["regions_land"]
    Crd = param["Crd"]
    res = param["res"]
    GeoRef = param["GeoRef"]
    m = param["m"]
    n = param["n"]
    landuse = param["landuse"]
    nRegions = param["nRegions_land"]

    # Obtain weather matrices
    merraData = {}
    # Clearness index - stored variable CLEARNESS
    merraData["CLEARNESS"] = hdf5storage.read('CLEARNESS', paths["CLEARNESS"])
    merraData["CLEARNESS"] = merraData["CLEARNESS"][Ind[0, reg, 2] - 1:Ind[0, reg, 0],
                             Ind[0, reg, 3] - 1:Ind[0, reg, 1], :]
    # Temperature 2m above the ground - stored variable T2M
    merraData["T2M"] = hdf5storage.read('T2M', paths["T2M"])
    merraData["T2M"] = merraData["T2M"][Ind[0, reg, 2] - 1:Ind[0, reg, 0], Ind[0, reg, 3] - 1:Ind[0, reg, 1], :]

    # Calculate A matrices
    # A_lu
    with rasterio.open(paths["LU"]) as src:
        w = src.read(1, window=rasterio.windows.Window.from_slices(slice((m[1, -1] - Ind[1, reg, 0]),
                                                                         (m[1, -1] - Ind[1, reg, 2] + 1)),
                                                                   slice(Ind[1, reg, 3] - 1,
                                                                         Ind[1, reg, 1])))
    rasterData["A_lu"] = np.flipud(w)
    # A_Ross (Temperature coefficients for heating losses)
    rasterData["A_Ross"] = changem(rasterData["A_lu"], param["landuse"]["Ross_coeff"], param["landuse"]["type"]).astype(
        float) / 10000
    # A_albedo (Reflectivity coefficients)
    rasterData["A_albedo"] = changem(rasterData["A_lu"], param["landuse"]["albedo"], param["landuse"]["type"]).astype(
        float) / 100

    TS = np.zeros((8760, 1))
    FLH = np.zeros((m[1, reg], n[1, reg]))
    status = 0
    for hour in hours:
        if hour <= param["status_bar_limit"]:
            # Show progress of the simulation
            status = status + 1
            sys.stdout.write('\r')
            sys.stdout.write(str(reg + 1) + '/' + str(nRegions) + ' ' + region_name + ' ' + '[%-50s] %d%%' % (
            '=' * ((status * 50) // len(hours)), (status * 100) // len(hours)))
            sys.stdout.flush()

        if tech == 'PV':
            CF, _ = calc_CF_solar(hour, reg, param, merraData, rasterData, 'Surface')
        elif tech == 'CSP':
            _, CF = calc_CF_solar(hour, reg, param, merraData, rasterData, 'Surface')

        # Aggregates CF to obtain the yearly FLH
        CF = CF * rasterData["A_region"]
        CF[np.isnan(CF)] = 0
        FLH = FLH + CF
        # Time series for the mean
        TS[hour] = np.mean(CF[rasterData["A_region"] == 1])
    print('\n')
    return FLH, TS


def calc_TS_solar(hours, args):
    # Decomposing the tuple args
    reg = args[0]
    paths = args[1]
    param = args[2]
    nRegions = args[3]
    region_name = args[4]
    rasterData = args[5]
    tech = args[6]

    Ind = param["Ind"]
    regions_shp = param["regions_land"]
    Crd = param["Crd"]
    res = param["res"]
    GeoRef = param["GeoRef"]
    m = param["m"]
    n = param["n"]
    landuse = param["landuse"]
    nRegions = param["nRegions_land"]

    # Obtain weather matrices
    merraData = {}
    # Downward shortwave radiation on the ground - stored variable SWGDN
    merraData["SWGDN"] = hdf5storage.read('SWGDN', paths["GHI"])
    merraData["SWGDN"] = merraData["SWGDN"][Ind[0, reg, 2]-1:Ind[0, reg, 0], Ind[0, reg, 3]-1:Ind[0, reg, 1], :]
    # Downward shortwave radiation at the top of the atmosphere SWTDN
    merraData["SWTDN"] = hdf5storage.read('SWTDN', paths["TOA"])
    merraData["SWTDN"] = merraData["SWTDN"][Ind[0, reg, 2]-1:Ind[0, reg, 0], Ind[0, reg, 3]-1:Ind[0, reg, 1], :]
    # Temperature 2m above the ground - stored variable T2M
    merraData["T2M"] = hdf5storage.read('T2M', paths["T2M"])
    merraData["T2M"] = merraData["T2M"][Ind[0, reg, 2]-1:Ind[0, reg, 0], Ind[0, reg, 3]-1:Ind[0, reg, 1], :]
		
    # Calculate A matrices
    # A_lu
    with rasterio.open(paths["LU"]) as src:
        w = src.read(1, window=rasterio.windows.Window.from_slices(slice((m[1, -1] - Ind[1, reg, 0]),
                                                                         (m[1, -1] - Ind[1, reg, 2] + 1)),
                                                                   slice(Ind[1, reg, 3] - 1,
                                                                         Ind[1, reg, 1])))
    rasterData["A_lu"] = np.flipud(w)
    # A_topo
    with rasterio.open(paths["TOPO"]) as src:
        w = src.read(1, window=rasterio.windows.Window.from_slices(slice((m[1, -1] - Ind[1, reg, 0]),
                                                                         (m[1, -1] - Ind[1, reg, 2] + 1)),
                                                                   slice(Ind[1, reg, 3] - 1,
                                                                         Ind[1, reg, 1])))
    rasterData["A_topo"] = np.flipud(w)
    # A_Ross (Temperature coefficients for heating losses)
    rasterData["A_Ross"] = changem(rasterData["A_lu"], param["landuse"]["Ross_coeff"], param["landuse"]["type"]).astype(
        float) / 10000
    # A_albedo (Reflectivity coefficients)
    rasterData["A_albedo"] = changem(rasterData["A_lu"], param["landuse"]["albedo"], param["landuse"]["type"]).astype(
        float) / 100

    TS = np.zeros((8760, 1))
    FLH = np.zeros((m[1, reg], n[1, reg]))

    for hour in hours:
        # Show progress of the simulation
        print(str(reg + 1) + '/' + str(nRegions) + ' ' + region_name + ' ' + str(hour + 1))

        if tech == 'PV':
            CF, _ = calc_CF_solar(hour, reg, param, merraData, rasterData, 'Surface')
        elif tech == 'CSP':
            _, CF = calc_CF_solar(hour, reg, param, merraData, rasterData, 'Surface')

        # Aggregates CF to obtain the yearly FLH
        CF = CF * rasterData["A_region"]
        CF[np.isnan(CF)] = 0
        FLH = FLH + CF
        # Time series for the mean
        TS[hour] = np.mean(CF[rasterData["A_region"] == 1])
    return FLH, TS


def angles(hour, *args):
    """
    This function creates six matrices for the desired extent, that represent the elevation, tilt, azimuth and
    oerientation angles, in addition to the sunrise and sunset hours of every pixel with the desired resolution

    :param hour: hour rank in a year (from 1 to 8760
    :param args:
        set1
        north, east, south, west: desired geographic extent
        res: resolution of MERRA data & desired resolution in lat/lon
        Ext_in: extent of the global are of interest
        set2
        (lat, lon): latitude and longitude of all points of interest
    """

    # Initialization

    if len(args) == 5:  # Surface
        reg = args[0]
        Ext = args[1]
        m = args[2]
        n = args[3]
        res = args[4]

        # Vector of latitudes between (south) and (north), with resolution res[1,0]
        lat = np.arange((Ext[2] + res[1, 0] / 2), (Ext[0] - res[1, 0] / 2), res[1, 0])
        if lat.size == 0:
            lat = Ext[0]
            m = 1

        # Vector of longitudes between (west) and (east), with resolution res[1,1]
        lon = np.arange((Ext[3] + res[1, 1] / 2), (Ext[1] - res[1, 1] / 3), res[1, 1])
        if lon.size == 0:
            lon = Ext[1]
            n = 1

    elif len(args) == 1:  # points
        Locations = args[0]
        lat = Locations[:, 0].T  # north = south
        lon = Locations[:, 1].T  # east = west
        m = len(lat)
        n = len(lon)
    N = hour // 24 + 1
    hourofday = hour % 24 + 0.5

    # Calculation
    # Latitude angle
    if lat.ndim == 1:
        lat = lat[np.newaxis]
    phi = repmat(lat.T, 1, n)

    # Equation of Time (in hours)
    EOT = -0.128 * sind(N * 360 / 365.25 - 2.80) - 0.165 * sind(2 * N * 360 / 365.25 + 19.7)

    # Time Correction Factor (in hours)
    if lon.ndim == 1:
        lon = lon[np.newaxis]
    TC = EOT + lon / 15  # no correction factor for differences to GMT, because data is in GMT

    # Local Solar Time (in hours)
    omegast = repmat(hourofday + TC, m, 1)

    # Hour angle (in degrees)
    omega = 15 * (omegast - 12)

    # Declination angle
    delta = repmat(arcsind(0.3978 * sin(N * 2 * np.pi / 365.25 - 1.400 + 0.0355
                                        * sin(N * 2 * np.pi / 365.25 - 0.0489))), phi.shape[0], phi.shape[1])
    delta[phi < 0] = - delta[phi < 0]

    # Elevation angle (in degrees)
    alpha = arcsind(sind(delta) * sind(phi) + cosd(delta) * cosd(phi) * cosd(omega))

    # Optimal tilt angle (loosely based on Breyer 2010)
    beta = np.minimum(np.abs(phi), 55)  # The tilt angle is preferably equal to the latitude
    range_lat = np.logical_and(np.abs(phi) >= 35, np.abs(phi) < 65)
    beta[range_lat] = (beta[range_lat] - 35) / 65 * 55 + 35  # Tilt angle does not increase very quickly
    range_lat = np.logical_and(lat >= 35, lat < 65)
    range_lon = np.logical_and(lon >= -20, lon < 30)
    range_lat = repmat(range_lat, range_lon.shape[1], 1).T
    range_lon = repmat(range_lon, range_lat.shape[0], 1)
    beta[np.logical_and(range_lat, range_lon)] = (beta[np.logical_and(range_lat,
                                                                      range_lon)] - 35) / 65 * 45 + 35  # Europe
    range_lat = np.logical_and(lat >= 20, lat < 65)
    range_lon = np.logical_and(lon >= 75, lon < 140)
    range_lat = repmat(range_lat, range_lon.shape[1], 1).T
    range_lon = repmat(range_lon, range_lat.shape[0], 1)
    beta[np.logical_and(range_lat, range_lon)] = (beta[np.logical_and(range_lat,
                                                                      range_lon)] - 20) / 65 * 60 + 20  # Asia/China

    # Azimuth angle (in degrees)
    aux = np.maximum(np.minimum(sind(delta) * cosd(phi) - cosd(delta) * sind(phi) * cosd(omega) / cosd(alpha), 1), -1)
    aziam = arccosd(aux)
    azipm = 360 - aziam
    azi = aziam * ((omega < 0) * 1) + azipm * ((omega >= 0) * 1)

    # Orientation (in degrees)
    orientation = np.zeros(alpha.shape)  # Azimuth of the PV panel is zero for the Southern hemisphere
    orientation[phi < 0] = 180  # Azimuth of the PV panel is 180° for the Southern hemisphere

    # Sunrise and sunset hours in GMT
    # aux = np.maximum(np.minimum((-tand(phi)) * tand(delta), 1), -1)
    aux = np.maximum(np.minimum((-tand(phi)) * tand(delta), 1), -1)
    sunrise = 12 - 1 / 15 * arccosd(aux)
    sunset = 12 + 1 / 15 * arccosd(aux)
    coeff_a = (cosd(phi) / tand(beta)) + sind(phi)
    coeff_b = tand(delta) * (cosd(phi) * cosd(orientation) - sind(phi) / tand(beta))
    aux = np.maximum(np.minimum(((coeff_a * coeff_b - sind(orientation)
                                  * (coeff_a ** 2 - coeff_b ** 2 + sind(orientation) ** 2) ** 0.5
                                  / (coeff_a ** 2 + sind(orientation) ** 2))), 1), -1)
    sunrise_tilt = 12 - 1 / 15 * arccosd(aux)
    sunset_tilt = 12 + 1 / 15 * arccosd(aux)

    # import pdb; pdb.set_trace()
    sunrise = np.maximum(sunrise, sunrise_tilt) - repmat(TC, m, 1)  # Correction Solar time -> GMT
    sunset = np.minimum(sunset, sunset_tilt) - repmat(TC, m, 1)  # Correction solar time -> GMT

    if len(args) == 1:
        phi = np.diag(phi)
        omega = np.diag(omega)
        delta = np.diag(delta)
        alpha = np.diag(alpha)
        beta = np.diag(beta)
        azi = np.diag(azi)
        orientation = np.diag(orientation)
        sunrise = np.diag(sunrise)
        sunset = np.diag(sunset)

    return phi, omega, delta, alpha, beta, azi, orientation, sunrise, sunset


def toa_hourly(alpha, *args):
    solarconst = 1367  # in W/m^2

    if len(args) >= 2:
        # Calculate day rank in the year
        month = args[0]
        dayofmonth = args[1]
        DoM = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])
        N = dayofmonth  # initialization
        for ii in range(0, len(month)):
            if month[ii] != 1:
                N[ii] = dayofmonth[ii] + np.sum(DoM[1:month[ii] - 1], 2)

    if len(args) == 1:
        hour = args[0]
        N = np.floor((hour - 1) / 24) + 1

    h_TOA = solarconst * (1 + 0.03344 * cos(N * 2 * np.pi / 365.25 - 0.048869)) * sin(np.deg2rad(alpha))

    return h_TOA


def coefficients(beta, ratio, R_b, A_i, f, *args):
    """
    This function creates three weighting matrices for the desired extent and with the desired resolution,
    that correspond to the gains/losses caused by tilting to each component of the incident radiation
    (direct, diffuse, and reflected

    The Input arguements are:
    - alpha: matrix of elevation angles
    - beta: matrix of tilting angles
    - azi: matrix of azimuth angles
    - orientation: matrix of surface azimuth (PV panel orientation angle)
    - hour, sunrise, and sunset (optional): hour of the year, and the matrix for the sunrise and sunset hours for every
    location on that day
    """

    duration = np.ones(beta.shape)  # Adjusts for any inaccuracy in case the sunset or the sunrise occurs within hour

    if len(args) == 3:
        hour = args[0]
        sunrise = args[1]
        sunset = args[2]
        hourofday = hour % 24 + 0.5

        # Case 1: Sunrise and sunset occur on the same day (GMT)
        critertion = np.logical_and(hourofday < sunrise, np.logical_and(sunrise > 0, sunset < 24))
        duration[critertion] = 0
        critertion = np.logical_and(np.logical_and((hourofday - 1) < sunrise, hourofday > sunrise),
                                    np.logical_and(sunrise > 0, sunset < 24))
        duration[critertion] = hourofday - sunrise[critertion]
        critertion = np.logical_and(np.logical_and((hourofday - 1) < sunset, hourofday > sunset),
                                    np.logical_and(sunrise > 0, sunset < 24))
        duration[critertion] = sunset[critertion] - hourofday + 1
        critertion = np.logical_and((hourofday - 1) > sunset,
                                    np.logical_and(sunrise > 0, sunset < 24))
        duration[critertion] = 0

        # Case 2: Sunrise occurs on the previous day (GMT) -
        # we can assume that it occurs at the same time as the following day
        critertion = np.logical_and(np.logical_and((hourofday - 1) < sunset, hourofday > sunset),
                                    np.logical_and(sunrise < 0, sunset < 24))
        duration[critertion] = sunset[critertion] - hourofday + 1
        critertion = np.logical_and(np.logical_and((hourofday - 1) > sunset, hourofday < sunrise + 24),
                                    np.logical_and(sunrise < 0, sunset < 24))
        duration[critertion] = 0
        critertion = np.logical_and(np.logical_and((hourofday - 1) < (sunrise + 24), hourofday > (sunrise + 24)),
                                    np.logical_and(sunrise < 0, sunset < 24))
        duration[critertion] = hourofday - (sunrise[critertion] + 24)

        # case 3: Sunset occurs on the next day (GMT) - not relevant for ASEAN
        critertion = np.logical_and(np.logical_and((hourofday - 1) < (sunset - 24), hourofday > (sunset - 24)),
                                    np.logical_and(sunrise > 0, sunset > 24))
        duration[critertion] = (sunset[critertion] - 24) - hourofday + 1
        critertion = np.logical_and(np.logical_and((hourofday - 1) > (sunset - 24), hourofday < sunrise),
                                    np.logical_and(sunrise > 0, sunset > 24))
        duration[critertion] = 0
        critertion = np.logical_and(np.logical_and((hourofday - 1) < sunrise, hourofday > sunrise),
                                    np.logical_and(sunrise > 0, sunset > 24))
        duration[critertion] = hourofday - sunrise[critertion]

    F_direct = duration * (1 - ratio + ratio * A_i) * R_b
    F_direct[F_direct < 0] = 0

    F_diffuse = ratio * (1 - A_i) * (1 + cos(np.deg2rad(beta))) / 2 * (1 + f * sin(np.deg2rad(beta / 2)) ** 3)

    F_reflected = (1 - cos(np.deg2rad(beta))) / 2

    return F_direct, F_diffuse, F_reflected


def loss(G_tilt_h, TEMP, A_Ross, pv):
    # This code creates a temperature loss weighting matrix for the desired extent
    # The inputs are:
    # G_tilt_h: incident radiation on the tilted panel
    # TEMP: matrix of ambient temperatures in °C
    # T_r: rated temperature according to STC
    # loss_coeff: % Heat loss coefficient according to the technical characteristics of the Yingli PV module

    T_cell = TEMP + A_Ross * G_tilt_h  # Cell temperature
    LOSS_TEMP = np.max(T_cell - pv["T_r"], 0) * pv["loss_coeff"] / 100
    return LOSS_TEMP


def global2diff(k_t, dims):
    # This code estimates the global-to-diffuse ratio.
    # The inputs are:

    k_d = np.zeros(dims)
    criterion = k_t <= 0.22
    k_d[criterion] = 1 - 0.09 * k_t[criterion]

    criterion = np.logical_and(k_t > 0.22, k_t <= 0.8)
    k_d[criterion] = 0.9511 - 0.1604 * k_t[criterion] + 4.388 * k_t[criterion] ** 2 - 16.638 * k_t[criterion] ** 3 \
                     + 12.336 * k_t[criterion] ** 4

    criterion = k_t > 0.8
    k_d[criterion] = 0.165

    A_ratio = np.minimum(k_d, 1)

    return A_ratio


def calc_CF_wind(hour, reg, turbine, m, n, merraData, rasterData):
    ''' This function calculates the capacity factor for a given wind speed at 50m'''

    # Load MERRA data, increase its resolution, and fit it to the extent
    w50m_h = resizem(merraData["W50M"][:, :, hour], m[1, reg], n[1, reg])

    # Calculate the wind speed a the desired height
    w_new_h = w50m_h * rasterData["A_cf"]
    del w50m_h

    # Calculate the capacity factor

    a = turbine["w_in"] ** 3 / (turbine["w_in"] ** 3 - turbine["w_r"] ** 3)
    b = 1 / (turbine["w_r"] ** 3 - turbine["w_in"] ** 3)

    CF = np.zeros(w_new_h.shape)
    # Case 1 : above the cut-in speed and below the rated speed
    idx1 = np.logical_and(turbine["w_in"] < w_new_h, w_new_h < turbine["w_r"])
    CF[idx1] = a + b * w_new_h[idx1] ** 3
    # Case 2 : above the rated wind speed and below the cut_off speed
    idx2 = np.logical_and(turbine["w_r"] <= w_new_h, w_new_h <= turbine["w_off"])
    CF[idx2] = 1
    # Other cases (below cut-in or above cut-off
    CF[np.logical_not(np.logical_or(idx1, idx2))] = 0

    return CF


def calc_FLH_wind(hours, args):
    # Decomposing the tuple args
    reg = args[0]
    paths = args[1]
    param = args[2]
    nRegions = args[3]
    region_name = args[4]
    rasterData = args[5]
    tech = args[6]

    if tech == "WindOff":
        regions_shp = param["regions_eez"]
        Ind = param["Ind"][:, -nRegions - 1:-1, :]
        m = param["m"][:, -nRegions - 1:]
        n = param["n"][:, -nRegions - 1:]
    else:
        regions_shp = param["regions_land"]
        Ind = param["Ind"][:, 0:nRegions, :]
        m = param["m"][:, 0:nRegions]
        m = np.c_[m, param["m"][:, -1]]
        n = param["n"][:, 0:nRegions]
        n = np.c_[n, param["n"][:, -1]]
    turbine = param[tech]["technical"]

    # Obtain weather matrices
    merraData = {}
    # Downward shortwave radiation on the ground - stored variable SWGDN
    merraData["W50M"] = hdf5storage.read('W50M', paths["W50M"])
    merraData["W50M"] = merraData["W50M"][Ind[0, reg, 2] - 1:Ind[0, reg, 0], Ind[0, reg, 3] - 1:Ind[0, reg, 1], :]

    # Calculate A matrices
    # A_cf
    with rasterio.open(paths["CORR"]) as src:
        w = src.read(1, window=rasterio.windows.Window.from_slices(slice((m[1, -1] - Ind[1, reg, 0]),
                                                                         (m[1, -1] - Ind[1, reg, 2] + 1)),
                                                                   slice(Ind[1, reg, 3] - 1,
                                                                         Ind[1, reg, 1])))
    rasterData["A_cf"] = np.flipud(w)

    TS = np.zeros((8760, 1))
    FLH = np.zeros((m[1, reg], n[1, reg]))
    status = 0
    for hour in hours:
        if hour <= param["status_bar_limit"]:
            # Show progress of the simulation
            status = status + 1
            sys.stdout.write('\r')
            sys.stdout.write(str(reg + 1) + '/' + str(nRegions) + ' ' + region_name + ' ' + '[%-50s] %d%%' % (
            '=' * ((status * 50) // len(hours)), (status * 100) // len(hours)))
            sys.stdout.flush()

        # Calculate hourly capacity factor
        CF = calc_CF_wind(hour, reg, turbine, m, n, merraData, rasterData)

        # Aggregates CF to obtain the yearly FLH
        CF = CF * rasterData["A_region"]
        CF[np.isnan(CF)] = 0
        FLH = FLH + CF
        # Time series for the mean
        TS[hour] = np.mean(CF[rasterData["A_region"] == 1])
    print('\n')
    return FLH, TS

""" SED fitting class using emcee for parameter estimation

.. moduleauthor:: Greg Zeimann <gregz@astro.as.utexas.edu>

"""
import logging
import sfh
import dust_abs
import dust_emission
import metallicity
import cosmology
import emcee
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import corner
import time
from scipy.integrate import simps
from scipy.interpolate import interp1d
from astropy.constants import c as clight
import numpy as np

plt.ioff() # UNCOMMENT THIS LINE IF RUNNING ON LINUX

import seaborn as sns
sns.set_context("talk") # options include: talk, poster, paper
sns.set_style("ticks")
sns.set_style({"xtick.direction": "in","ytick.direction": "in",
               "xtick.top":True, "ytick.right":True,
               "xtick.major.size":12, "xtick.minor.size":4,
               "ytick.major.size":12, "ytick.minor.size":4,
               })




#WPBWPB re organize the arguments (aesthetic purposes)
class Mcsed:
    def __init__(self, filter_matrix, ssp_spectra,
                 emlinewave, ssp_emline, ssp_ages,
                 ssp_met, wave, sfh_class, dust_abs_class, dust_em_class,
                 data_fnu=None, data_fnu_e=None, 
                 data_emline=None, data_emline_e=None, emline_dict=None,
                 redshift=None,
                 filter_flag=None, input_spectrum=None, input_params=None,
                 sigma_m=0.1, nwalkers=40, nsteps=1000, true_fnu=None, 
                 chi2=None, TauISM_lam=None, TauIGM_lam=None):
        ''' Initialize the Mcsed class.

        Init
        ----
        filter_matrix : numpy array (2 dim)
            The filter_matrix has rows of wavelength and columns for each
            filter (can be much larger than the filters used for fitting)
        ssp_spectra : numpy array (3 dim)
            single stellar population spectrum for each age in ssp_ages
            and each metallicity in ssp_met 
        emlinewave : numpy array (1 dim)
            Rest-frame wavelengths of requested emission lines (emline_dict)
            Corresponds to ssp_emline
        ssp_emline : numpy array (3 dim)
            Emission line SSP grid spanning emlinewave, age, metallicity
            Only includes requested emission lines (from emline_dict)
            Only used for calculating model emission line strengths
            Spectral units are ergs / s / cm2 at 10 pc
        ssp_ages : numpy array (1 dim)
            ages of the SSP models
        ssp_met : numpy array (1 dim)
            metallicities of the SSP models
            assume a grid of values Z, where Z_solar = 0.019
        wave : numpy array (1 dim)
            wavelength for SSP models and all model spectra
        sfh_class : str
            Converted from str to class in initialization
            This is the input class for sfh.  Each class has a common attribute
            which is "sfh_class.get_nparams()" for organizing the total model_params.
            Also, each class has a key function, sfh_class.evaluate(t), with
            the input of time in units of Gyrs
        dust_abs_class : str 
            Converted from str to class in initialization
            This is the input class for dust absorption.
        dust_em_class : str
            Converted from str to class in initialization
            This is the input class for dust absorption.
        data_fnu : numpy array (1 dim)
            Photometry for data.  Length = (filter_flag == True).sum()
WPBWPB units + are dimensions correct??
        data_fnu_e : numpy array (1 dim)
            Photometric errors for data
        data_emline : Astropy Table (1 dim)
            Emission line fluxes in units ergs / cm2 / s
        data_emline_e : Astropy Table (1 dim)
            Emission line errors in units ergs / cm2 / s
        emline_dict : dictionary
            Keys are emission line names (str)
            Values are a two-element tuple:
                (rest-frame wavelength in Angstroms (float), weight (float))
        use_emline_flux : bool
            If emline_dict contains emission lines, set to True. Else, False
        redshift : float
            Redshift of the source
        filter_flag : numpy array (1 dim)
            Length = filter_matrix.shape[1], True for filters matching data
        input_spectrum : numpy array (1 dim)
            F_nu(wave) for input
        input_params : list
            input parameters for modeling.  Intended for testing fitting
            procedure.
        sigma_m : float
            Fractional error expected from the models.  This is used in
            the log likelihood calculation.  No model is perfect, and this is
            more or less a fixed parameter to encapsulate that.
        nwalkers : int
            The number of walkers for emcee when fitting a model
        nsteps : int
            The number of steps each walker will make when fitting a model
        true_fnu : WPBWPB FILL IN
        chi2 : WPBWPB FILL IN
        TauISM_lam : numpy array (1 dim)
            Array of effective optical depths as function of wavelength for MW dust correction
        TauIGM_lam : numpy array (1 dim)
            Array of effective optical depths as function of wavelength for IGM gas correction


WPBWPB: describe self.t_birth, set using args and units of Gyr
        '''
        # Initialize all argument inputs
        self.filter_matrix = filter_matrix
        self.ssp_spectra = ssp_spectra
        self.emlinewave = emlinewave
        self.ssp_emline = ssp_emline
        self.ssp_ages = ssp_ages
        self.ssp_met = ssp_met
        self.wave = wave
        self.dnu = np.abs(np.hstack([0., np.diff(2.99792e18 / self.wave)]))
        self.sfh_class = getattr(sfh, sfh_class)()
        self.dust_abs_class = getattr(dust_abs, dust_abs_class)()
        self.met_class = getattr(metallicity, 'stellar_metallicity')()
        self.dust_em_class = getattr(dust_emission, dust_em_class)()
# WPBWPB: describe SSP, lineSSP in comments... 
# ssp_spectra span many metallicities, SSP only span ages
        self.SSP = None
        self.lineSSP = None
        self.param_classes = ['sfh_class', 'dust_abs_class', 'met_class',
                              'dust_em_class']
        self.data_fnu = data_fnu
        self.data_fnu_e = data_fnu_e
        self.data_emline = data_emline
        self.data_emline_e = data_emline_e
        self.emline_dict = emline_dict
        self.redshift = redshift
        self.filter_flag = filter_flag
        self.input_spectrum = input_spectrum
        self.input_params = input_params
        self.sigma_m = sigma_m
        self.nwalkers = nwalkers
        self.nsteps = nsteps
        self.true_fnu = true_fnu
        self.TauISM_lam = TauISM_lam
        self.TauIGM_lam = TauIGM_lam
        if self.redshift is not None:
            self.set_new_redshift(self.redshift)
        self.chi2 = chi2

        # Set up logging
        self.setup_logging()

        # Time array for sfh
        self.age_eval = np.logspace(-3, 1, 4000)

    def set_new_redshift(self, redshift):
        ''' Setting redshift

        Parameters
        ----------
        redshift : float
            Redshift of the source for fitting
        '''
        self.redshift = redshift
        # Need luminosity distance to adjust ssp_spectra from 10pc to Dl
        self.Dl = cosmology.Cosmology().luminosity_distance(self.redshift)
        self.sfh_class.set_agelim(self.redshift)

    def setup_logging(self):
        '''Setup Logging for MCSED

        Builds
        -------
        self.log : class
            self.log.info() is for general print and self.log.error() is
            for raise cases
        '''
        self.log = logging.getLogger('mcsed')
        if not len(self.log.handlers):
            # Set format for logger
            fmt = '[%(levelname)s - %(asctime)s] %(message)s'
            fmt = logging.Formatter(fmt)
            # Set level of logging
            level = logging.INFO
            # Set handler for logging
            handler = logging.StreamHandler()
            handler.setFormatter(fmt)
            handler.setLevel(level)
            # Build log with name, mcsed
            self.log = logging.getLogger('mcsed')
            self.log.setLevel(logging.DEBUG)
            self.log.addHandler(handler)

    def remove_waverange_filters(self, wave1, wave2, restframe=True):
        '''Remove filters in a given wavelength range

        Parameters
        ----------
        wave1 : float
            start wavelength of masked range (in Angstroms)
        wave2 : float
            end wavelength of masked range (in Angstroms)
        restframe : bool
            if True, wave1 and wave2 correspond to rest-frame wavelengths
        '''
        wave1, wave2 = np.sort([wave1, wave2])
        if restframe:
            wave_factor = 1. + self.redshift
        else:
            wave_factor = 1.
        loc1 = np.searchsorted(self.wave, wave1 * wave_factor)
        loc2 = np.searchsorted(self.wave, wave2 * wave_factor)
        # account for the case where indices are the same
        if (loc1 == loc2):
            loc2+=1
        maxima = np.max(self.filter_matrix, axis=0)
        try:
            newflag = np.max(self.filter_matrix[loc1:loc2, :], axis=0) < maxima * 0.1
        except ValueError:
            return
        maximas = np.max(self.filter_matrix[:, self.filter_flag], axis=0)
        newflags = np.max(self.filter_matrix[loc1:loc2, self.filter_flag], axis=0) < maximas * 0.1
        self.filter_flag = self.filter_flag * newflag
        if self.true_fnu is not None:
            self.true_fnu = self.true_fnu[newflags]
        self.data_fnu = self.data_fnu[newflags]
        self.data_fnu_e = self.data_fnu_e[newflags]


    def get_filter_wavelengths(self):
        ''' FILL IN
        '''
        wave_avg = np.dot(self.wave, self.filter_matrix[:, self.filter_flag])
        return wave_avg

    def get_filter_fluxdensities(self):
        '''Convert a spectrum to photometric fluxes for a given filter set.
        The photometric fluxes will be in the same units as the spectrum.
        The spectrum is in microjanskies(lambda) such that
        the photometric fluxes will be in microjanskies.

        Returns
        -------
        f_nu : numpy array (1 dim)
            Photometric flux densities for an input spectrum
        '''
## WPBWPB delete
#        print('shape of spectrum, filter_matrix, filter_flag:')
#        print((self.spectrum.shape, self.filter_matrix.shape, self.filter_flag.shape))
        f_nu = np.dot(self.spectrum, self.filter_matrix[:, self.filter_flag])
        return f_nu


    def measure_absorption_index(self):
        '''
        measure absorption indices using current spectrum


        '''
        self.absindxCSPdict = {}
        if self.use_absorption_indx:
            # convert the spectrum from units of specific frequency to specific wavelength
            wave = self.wave.copy()
            factor = clight.to('Angstrom/s').value / wave**2.
            spec = self.spectrum * factor

            for indx in self.absindx_dict.keys():
                wht, wave_indx, wave_blue, wave_red, unit = self.absindx_dict[indx]

                # select appropriate data ranges for blue/red continuum and index
                sel_index = np.array([False]*len(wave))
                sel_index[np.argmin(abs(wave-wave_indx[0])):np.argmin(abs(wave-wave_indx[1]))] = True
                if abs(np.argmin(abs(wave-wave_indx[0]))-np.argmin(abs(wave-wave_indx[1])))<2:
                    sel_index[np.argmin(abs(wave-wave_indx[0])):np.argmin(abs(wave-wave_indx[0]))+2] = True
                sel_blue = np.array([False]*len(wave))
                sel_blue[np.argmin(abs(wave-wave_blue[0])):np.argmin(abs(wave-wave_blue[1]))] = True
                if abs(np.argmin(abs(wave-wave_blue[0]))-np.argmin(abs(wave-wave_blue[1])))<2:
                    sel_blue[np.argmin(abs(wave-wave_blue[0])):np.argmin(abs(wave-wave_blue[0]))+2] = True
                sel_red = np.array([False]*len(wave))
                sel_red[np.argmin(abs(wave-wave_red[0])):np.argmin(abs(wave-wave_red[1]))] = True
                if abs(np.argmin(abs(wave-wave_red[0]))-np.argmin(abs(wave-wave_red[1])))<2:
                    sel_red[np.argmin(abs(wave-wave_red[0])):np.argmin(abs(wave-wave_red[0]))+2] = True

#                sel_index = (wave >= wave_indx[0]) & (wave <= wave_indx[1])
#                sel_blue  = (wave >= wave_blue[0]) & (wave <= wave_blue[1])
#                sel_red   = (wave >= wave_red[0])  & (wave <= wave_red[1])

                # estimate continuum in the index:
                fw_blue  = np.dot(spec[sel_blue][0:-1], np.diff(wave[sel_blue])) 
                fw_blue /= np.diff(wave[sel_blue][[0,-1]])
                fw_red   = np.dot(spec[sel_red][0:-1],  np.diff(wave[sel_red]))  
                fw_red  /= np.diff(wave[sel_red][[0,-1]])
                cont_waves = [np.median(wave_blue), np.median(wave_red)]
                cont_fw    = [fw_blue, fw_red]
                coeff = np.polyfit( cont_waves, cont_fw, 1)
                cont_index = coeff[0] * wave[sel_index] + coeff[1]

                # flux ratio of index and continuum
                spec_index = spec[sel_index] / cont_index

                if unit==0: # return measurement in equivalent width
                    value = np.dot( 1. - spec_index[0:-1], np.diff(wave[sel_index]) )

                if unit==1: # return measurement in magnitudes
                    integral = np.dot( spec_index[0:-1], np.diff(wave[sel_index]) )
                    value = -2.5 * np.log10( integral / np.diff(wave[sel_index][[0,-1]]) ) 

                if unit==2: # return measurement as a flux density ratio (red / blue)
                    value = fw_red / fw_blue

                self.absindxCSPdict[indx] = float(value)


    def set_class_parameters(self, theta):
        ''' For a given set of model parameters, set the needed class variables
        related to SFH, dust attenuation, ect.

        Input
        -----
        theta : list
            list of input parameters for sfh, dust att., and dust em.
        '''
        start_value = 0
        ######################################################################
        # STAR FORMATION HISTORY
        self.sfh_class.set_parameters_from_list(theta, start_value)
        # Keeping track of theta index for age of model and other classes
        start_value += self.sfh_class.get_nparams()

        ######################################################################
        # DUST ATTENUATION
        self.dust_abs_class.set_parameters_from_list(theta, start_value)
        start_value += self.dust_abs_class.get_nparams()
# WPBWPB modify: pass a dust_abs_birthcloud keyword, see if its the same, blah

        ######################################################################
        # SSP Parameters
## WPBWPB delete
#        print(start_value)
        self.met_class.set_parameters_from_list(theta, start_value)
        start_value += self.met_class.get_nparams()
## WPBWPB delete
#        print(start_value)
        ######################################################################
        # DUST EMISSION
        self.dust_em_class.set_parameters_from_list(theta, start_value)
        start_value += self.dust_em_class.get_nparams()

#        print('this is start_value (is it equal to number of free params?)')
#        print(start_value)
#        print(len(theta))
        # set self.nparams -- number of parameters in the model

    def get_ssp_spectrum(self):
        '''
        Calculate SSP for an arbitrary metallicity (self.met_class.met) given a
        model grid for a range of metallicities (self.ssp_met)

        if left as a free parameter, stellar metallicity (self.met_class.met)
        spans a range of log(Z / Z_solar)

        the SSP grid of metallicities (self.ssp_met) assumes values of Z
        (as opposed to log solar values)

        Returns
        -------
        SSP : 2-d array
            Single stellar population models for each age in self.ages
        lineSSP : 2-d array
            Single stellar population line fluxes for each age in self.ages

        '''
        if self.met_class.fix_met:
            if self.SSP is not None:
## WPBWPB delete
#                print('self.SSP is not None!')
                return self.SSP, self.lineSSP
        Z = np.log10(self.ssp_met)
        Zsolar = 0.019
        z = self.met_class.met + np.log10(Zsolar)
        X = Z - z
        wei = np.exp(-(X)**2 / (2. * 0.15**2))
        wei /= wei.sum()
        self.SSP = np.dot(self.ssp_spectra, wei)
# WPBWPB: this is where I would relax logU criteria, same as metallicity
# careful: needs to be dealt with when measuring line fluxes originally

        # only treat the emission line grid if requested
## WPBWPB delete
#        print('shape of emline SSP before/after wei')
#        print(self.ssp_emline.shape)
        if self.use_emline_flux:
            self.lineSSP = np.dot(self.ssp_emline, wei)
        else:
            self.lineSSP = self.ssp_emline[:,:,0]
## WPBWPB delete
#        print(self.lineSSP.shape)
        return self.SSP, self.lineSSP

    def build_csp(self, sfr=None):
        '''Build a composite stellar population model for a given star
        formation history, dust attenuation law, and dust emission law.

        In addition to the returns it also modifies a lineflux dictionary

        Returns
        -------
        csp : numpy array (1 dim)
            Composite stellar population model (micro-Jy) at self.redshift
        mass : float
            Mass for csp given the SFH input
        '''
        # Collapse for metallicity
        SSP, lineSSP = self.get_ssp_spectrum()

        # Need star formation rate from observation back to formation
        if sfr is None:
            sfr = self.sfh_class.evaluate(self.ssp_ages)
        ageval = 10**self.sfh_class.age # Gyr

## WPBWPB delete
#        print('these are the sfr in SFH age grid in Gyr:')
#        sfh_ages = 10.**(np.array(self.sfh_class.ages)-9.)
#        print(sfh_ages)
#        print(self.sfh_class.evaluate(sfh_ages))

        # Treat the birth cloud and diffuse component separately
# WPBWPB: may want to modify: have this as user-defined setting...
        age_birth = self.t_birth #10**-2 # Gyr 

### WPBWPB delete - both in Gyr
##        print('this is the ageval: %s' % ageval)
##        print('this is ssp ages: %s' % self.ssp_ages)
##        return

## WPBWPB delete
##        for ageval, age_birth in [ [0.008, 0.011 ], [0.005011872336272725, 0.011 ], [0.01, 0.011 ], [0.14, 0.011 ], [0.0116, 0.011 ], [0.1, 0.011 ], [0.0145, 0.01 ], [0.011, 0.011 ], [0.01, 0.01 ] ]:
#        for ageval, age_birth in [ [0.01116, 0.011] ]:
#            self.build_dustfree_CSP(sfr, ageval, age_birth)
#        return

        # Get dust-free CSPs, properly accounting for ages
        # ageval sets limit on ssp_ages that are useable in model calculation
        # age_birth separates birth cloud and diffuse components
# WPBWPB delete -- ageval, ssp_ages, age_birth are in units Gyr
        sel = (self.ssp_ages > age_birth) & (self.ssp_ages <= ageval)
        sel_birth = (self.ssp_ages <= age_birth) & (self.ssp_ages <= ageval)
        sel_age = self.ssp_ages <= ageval

        # The weight is the time between ages of each SSP
        weight = np.diff(np.hstack([0, self.ssp_ages])) * 1e9 * sfr
# WPBWPB delete
        weight_orig = weight.copy()
        weight_birth = weight.copy()
        weight_age = weight.copy()
        # Ages greater than ageval should have zero weight in CSP
        # weight should only include populations younger than ageval
        # and older than age_birth
        # weight_birth should only include populations younger than ageval
        # and no older than age_birth
        # weight_age only considers the age of the system (for mass)
        weight[~sel] = 0
        weight_birth[~sel_birth] = 0
        weight_age[~sel_age] = 0

        # Cover the two cases where ssp_ages contains ageval and when not
        # A: index of last acceptable SSP age
        A = np.nonzero(self.ssp_ages <= ageval)[0][-1]
        # indices of SSP ages that are too old
        select_too_old = np.nonzero(self.ssp_ages >= ageval)[0]
        if len(select_too_old):
            # B: index of first SSP that is too old
            B = select_too_old[0]
            # only adjust weight if ageval falls between two SSP age gridpoints
            if A != B:
                lw = ageval - self.ssp_ages[A]
                wei = lw * 1e9 * np.interp(ageval, self.ssp_ages, sfr)
                if ageval > age_birth:
                    weight[B] = wei
                if ageval <= age_birth:
                    weight_birth[B] = wei
                weight_age[B] = wei

        # Cover two cases where ssp_ages contains age_birth and when not
        # A: index of last acceptable SSP age
        A = np.nonzero(self.ssp_ages <= age_birth)[0][-1]
        # indices of SSP ages that are too old
        select_too_old = np.nonzero(self.ssp_ages >= age_birth)[0]
        if (len(select_too_old)>0): # & (ageval>=age_birth):
            # B: index of first SSP that is too old
            B = select_too_old[0]
            if A != B:
                lw = age_birth - self.ssp_ages[A]
                wei = lw * 1e9 * np.interp(age_birth, self.ssp_ages, sfr)
                if ageval > age_birth:
                    weight[B] = weight_age[B] - wei
                if ageval >= age_birth:
                    weight_birth[B] = wei
                else:
                    weight_birth[B] = weight_age[B]

        # Finally, do the matrix multiplication using the weights
        #print("Max(SSP) = %.3e"%(np.amax(self.SSP)))
        spec_dustfree = np.dot(self.SSP, weight)
        spec_birth_dustfree = np.dot(self.SSP, weight_birth)
        linespec_dustfree = np.dot(self.lineSSP, weight_birth)
        mass = np.sum(weight_age)

        # Need to correct spectrum for dust attenuation
        Alam = self.dust_abs_class.evaluate(self.wave)
        spec_dustobscured = spec_dustfree * 10**(-0.4 * Alam)

        # Correct the corresponding birth cloud spectrum separately
# WPBWPB: check which law using for the birth cloud
# if attenuating it directly tied to overall dust law,
# modified by coefficient between EBV_stars ~ gas, get it here
        Alam_birth = Alam / self.dust_abs_class.EBV_old_young
        spec_birth_dustobscured = spec_birth_dustfree * 10**(-0.4 * Alam_birth)

        # Combine the young and old components
        spec_dustfree += spec_birth_dustfree
        spec_dustobscured += spec_birth_dustobscured

        # compute attenuation for emission lines
        Alam_emline = (self.dust_abs_class.evaluate(self.emlinewave,new_wave=True)
                       / self.dust_abs_class.EBV_old_young)
# WPBWPB: else, use a separate model

## WPBWPB delete
#        print(emwaves)
#        print(Alam_emline)
#        print('shape of linespec_dustfree, emwaves : (%s, %s)' % (linespec_dustfree.shape, emwaves.shape))
        linespec_dustobscured = linespec_dustfree * 10**(-0.4*Alam_emline)

## WPBWPB compare Alam in diffuse, birthcloud components
#        print('diffuse, birth, emline Alam:')
#        print(Alam[ np.searchsorted(self.wave, self.emlinewave) ])
#        print(Alam_birth[ np.searchsorted(self.wave, self.emlinewave) ])
#        print(Alam_emline)

        # Add dust emission
#        if min(spec_dustobscured[self.wave>5.0e4])<0.0: #Check to see that we don't have nonsensical results
# WPBWPB delete
#            print("Before adding dust: min(spec_dustobscured[wave>5.0 um]) =",
#                  min(spec_dustobscured[self.wave>5.0e4]))
        if self.dust_em_class.assume_energy_balance:
            L_bol = (np.dot(self.dnu, spec_dustfree) - np.dot(self.dnu, spec_dustobscured)) #Bolometric luminosity of dust attenuation (for energy balance)
            dust_em = self.dust_em_class.evaluate(self.wave)
            L_dust = np.dot(self.dnu,dust_em) #Bolometric luminosity of dust emission (but not yet multiplied by dust mass)
            # print("Lbol: %.3e;   Ldust: %.3e"%(L_bol,L_dust)) 
            mdust_eb = L_bol/L_dust #We want total luminosities to be same for absorption (attenuation) and emission; linear units for mdust_eb for now
            spec_dustobscured += mdust_eb * dust_em
        else:
            spec_dustobscured += self.dust_em_class.evaluate(self.wave)
        #print("After adding dust: min(spec_dustobscured[wave>5.0 um]) =",min(spec_dustobscured[self.wave>5.0e4]))

        # Redshift to observed frame
        csp = np.interp(self.wave, self.wave * (1. + self.redshift),
                        spec_dustobscured * (1. + self.redshift))

        # Correct for ISM and/or IGM (or neither)
        if self.TauIGM_lam is not None:
            csp *= np.exp(-self.TauIGM_lam)
        if self.TauISM_lam is not None:
            csp *= np.exp(-self.TauISM_lam)

        # Update dictionary of modeled emission line fluxes
        linefluxCSPdict = {}
        if self.use_emline_flux:
            for emline in self.emline_dict.keys():
                indx = np.argmin(np.abs(self.emlinewave 
                                        - self.emline_dict[emline][0]))
                # flux is given in ergs / s / cm2 at 10 pc
                flux = linespec_dustobscured[indx]
                # Correct flux from 10pc to redshift of source
                linefluxCSPdict[emline] = linespec_dustobscured[indx] / self.Dl**2
        self.linefluxCSPdict = linefluxCSPdict

## WPBWPB delete
#        print( linefluxCSPdict )

        # Correct spectra from 10pc to redshift of the source
        if self.dust_em_class.assume_energy_balance:
            return csp / self.Dl**2, mass, mdust_eb
        else:
            return csp / self.Dl**2, mass

    def lnprior(self):
        ''' Simple, uniform prior for input variables

        Returns
        -------
        0.0 if all parameters are in bounds, -np.inf if any are out of bounds
        '''
        flag = True
        for par_cl in self.param_classes:
            flag *= getattr(self, par_cl).prior()
        if not flag:
            return -np.inf
        else:
            return 0.0

    def lnlike(self):
        ''' Calculate the log likelihood and return the value and stellar mass
        of the model as well as other derived parameters

        Returns
        -------
        log likelihood, mass, sfr10, sfr100, fpdr, mdust_eb : float, float, float, float, float, float, float
            The log likelihood includes a chi2_term and a parameters term.
            The mass comes from building of the composite stellar population
            The parameters sfr10, sfr100, fpdr, mdust_eb are derived in get_derived_params(self)
        '''
        if self.dust_em_class.assume_energy_balance:
            self.spectrum, mass, mdust_eb = self.build_csp()
        else:
            self.spectrum, mass = self.build_csp()
            mdust_eb = None

        sfr10,sfr100,fpdr = self.get_derived_params()

        # likelihood contribution from the photometry
        model_y = self.get_filter_fluxdensities()
        inv_sigma2 = 1.0 / (self.data_fnu_e**2 + (model_y * self.sigma_m)**2)
        chi2_term = -0.5 * np.sum((self.data_fnu - model_y)**2 * inv_sigma2)
        parm_term = -0.5 * np.sum(np.log(1 / inv_sigma2))

        # calculate the degrees of freedom and store the current chi2 value
        # only need to calculate the degrees of freedom once
        if not self.chi2:
            dof_wht = list(np.ones(len(self.data_fnu)))


        # likelihood contribution from the absorption line indices
        self.measure_absorption_index()
        if self.use_absorption_indx:
            for indx in self.absindx_dict.keys():
                unit = self.absindx_dict[indx][-1]
                # if null value, ignore it (null = -99)
                if (self.data_absindx['%s_INDX' % indx]+99 > 1e-10):
                    indx_weight = self.absindx_dict[indx][0]
                    model_indx = self.absindxCSPdict[indx]
                    if unit == 1: # magnitudes
                        model_err = 2.5*np.log10(1.+self.sigma_m)
                    else:
                        model_err = model_indx * self.sigma_m
                    obs_indx = self.data_absindx['%s_INDX' % indx]
                    obs_indx_e = self.data_absindx_e['%s_Err' % indx]
                    sigma2 = obs_indx_e**2. + model_err**2.
                    chi2_term += (-0.5 * (model_indx - obs_indx)**2 /
                                  sigma2) * indx_weight
                    parm_term += -0.5 * np.log(indx_weight * sigma2)
                    if not self.chi2:
                        dof_wht.append(indx_weight) 
#                    print('this is absorption thing:')
#                    print((indx, obs_indx, obs_indx_e, model_indx, absindx_term))
#                    print((type(indx), type(obs_indx), type(obs_indx_e), type(model_indx), type(absindx_term)))

        # likelihood contribution from the emission lines
        if self.use_emline_flux:
            # if all lines have null line strengths, ignore 
            if not min(self.data_emline) == max(self.data_emline) == -99:
## WPBWPB delete
#                print('this is emline_dict:' + str(self.emline_dict))
#                print('this is emline data, error:')
#                print(self.data_emline)
#                print(self.data_emline_e)
                for emline in self.emline_dict.keys():
                    if self.data_emline['%s_FLUX' % emline] > -99: # null value
                        emline_wave, emline_weight = self.emline_dict[emline]
                        model_lineflux = self.linefluxCSPdict[emline]
                        model_err = model_lineflux * self.sigma_m
                        lineflux  = self.data_emline['%s_FLUX' % emline]
                        elineflux = self.data_emline_e['%s_ERR' % emline]
                        sigma2 = elineflux**2. + model_err**2.
                        chi2_term += (-0.5 * (model_lineflux - lineflux)**2 /
                                      sigma2) * emline_weight
                        parm_term += -0.5 * np.log(emline_weight * sigma2)
                        if not self.chi2:
                            dof_wht.append(emline_weight)

        # record current chi2 and degrees of freedom
        if not self.chi2:
            self.chi2 = {}
            dof_wht = np.array(dof_wht)
            npt = ( sum(dof_wht)**2. - sum(dof_wht**2.) ) / sum(dof_wht) + 1
            self.chi2['dof'] = npt - self.nfreeparams 
        self.chi2['chi2']  = -2. * chi2_term
        self.chi2['rchi2'] = self.chi2['chi2'] / (self.chi2['dof'] - 1.)

        if np.isnan(chi2_term + parm_term):
            print('lnlike is nanny, heres chi2 and parm:')
            print((chi2_term, parm_term))

        return (chi2_term + parm_term, mass,sfr10,sfr100,fpdr,mdust_eb)

    def lnprob(self, theta):
        ''' Calculate the log probabilty and return the value and stellar mass (as well as derived parameters)
        of the model

        Returns
        -------
        log prior + log likelihood, [mass,sfr10,sfr100,fpdr,mdust_eb]: float,float,float,float,float,float
            The log probability is just the sum of the logs of the prior and
            likelihood.  The mass comes from the building of the composite
            stellar population. The other derived parameters are calculated in get_derived_params()
        '''
        self.set_class_parameters(theta)
        lp = self.lnprior()
# WPBWPB delete
#        print('here is theta:')
#        print(theta)
#        print('here is lnprior:')
#        print(lp)
        if np.isfinite(lp):
            #lnl,mass,sfr10,sfr100,fpdr,mdust,mdust2 = self.lnlike()
            lnl,mass,sfr10,sfr100,fpdr,mdust_eb = self.lnlike()
            if not self.dust_em_class.fixed:
                if self.dust_em_class.assume_energy_balance:
                    return lp + lnl, np.array([mass,sfr10,sfr100,fpdr,mdust_eb])
                else:
                    return lp + lnl, np.array([mass, sfr10, sfr100, fpdr])
            else:
## WPBWPB delete
#                print('lp is finite. heres the output from lnprob:')
#                print( (lp + lnl, np.array([mass, sfr10, sfr100]) ) )
                return lp + lnl, np.array([mass, sfr10, sfr100])
        else:
## WPBWPB delete
#            print('I reached the else in lnprob')        
            if not self.dust_em_class.fixed:
                if self.dust_em_class.assume_energy_balance:
                    return -np.inf, np.array([-np.inf, -np.inf, -np.inf, -np.inf, -np.inf])
                else:
                    return -np.inf, np.array([-np.inf, -np.inf, -np.inf, -np.inf])
            else:
                return -np.inf, np.array([-np.inf, -np.inf, -np.inf])

    def get_init_walker_values(self, kind='ball', num=None):
        ''' Before running emcee, this function generates starting points
        for each walker in the MCMC process.

        Returns
        -------
        pos : np.array (2 dim)
            Two dimensional array with Nwalker x Ndim values
        '''
        # We need an initial guess for emcee so we take it from the model class
        # parameter values and deltas
        init_params, init_deltas, init_lims = [], [], []
        for par_cl in self.param_classes:
            init_params.append(getattr(self, par_cl).get_params())
            init_deltas.append(getattr(self, par_cl).get_param_deltas())
            if len(getattr(self, par_cl).get_param_lims()):
                init_lims.append(getattr(self, par_cl).get_param_lims())
        theta = list(np.hstack(init_params))
        thetae = list(np.hstack(init_deltas))
        theta_lims = np.vstack(init_lims)
        if num is None:
            num = self.nwalkers
        if kind == 'ball':
            pos = emcee.utils.sample_ball(theta, thetae, size=num)
        else:
            pos = (np.random.rand(num)[:, np.newaxis] *
                   (theta_lims[:, 1]-theta_lims[:, 0]) + theta_lims[:, 0])
        return pos

    def get_param_names(self):
        ''' Grab the names of the parameters for plotting

        Returns
        -------
        names : list
            list of all parameter names
        '''
        names = []
        for par_cl in self.param_classes:
            names.append(getattr(self, par_cl).get_names())
        names = list(np.hstack(names))
        return names

    def get_params(self):
        ''' Grab the the parameters in each class

        Returns
        -------
        vals : list
            list of all parameter values
        '''
        vals = []
        for par_cl in self.param_classes:
            vals.append(getattr(self, par_cl).get_params())
## WPBWPB delete
#            print(par_cl)
#            print(vals)
        vals = list(np.hstack(vals))
        self.nfreeparams = len(vals)
        return vals

    def get_param_lims(self):
        ''' Grab the limits of the parameters for making mock galaxies

        Returns
        -------
        limits : numpy array (2 dim)
            an array with parameters for rows and limits for columns
        '''
        limits = []
        for par_cl in self.param_classes:
            limits.append(getattr(self, par_cl).get_param_lims())
        limits = np.array(sum(limits, []))
        return limits

    def fit_model(self):
        ''' Using emcee to find parameter estimations for given set of
        data measurements and errors
        '''
        # Need to verify data parameters have been set since this is not
        # a necessity on initiation
        self.log.info('Fitting model using emcee')
        check_vars = ['data_fnu', 'data_fnu_e', 'redshift', 'filter_flag']
        for var in check_vars:
            if getattr(self, var) is None:
                self.error('The variable %s must be set first' % var)

        pos = self.get_init_walker_values(kind='ball')
        ndim = pos.shape[1]
        start = time.time()
        sampler = emcee.EnsembleSampler(self.nwalkers, ndim, self.lnprob,
                                        a=2.0)
        # Do real run
        sampler.run_mcmc(pos, self.nsteps, rstate0=np.random.get_state())
        end = time.time()
        elapsed = end - start
        self.log.info("Total time taken: %0.2f s" % elapsed)
        self.log.info("Time taken per step per walker: %0.2f ms" %
                      (elapsed / (self.nsteps) * 1000. /
                       self.nwalkers))
        # Calculate how long the run should last
        tau = np.max(sampler.acor)
        burnin_step = int(tau*3)
        self.log.info("Mean acceptance fraction: %0.2f" %
                      (np.mean(sampler.acceptance_fraction)))
        self.log.info("AutoCorrelation Steps: %i, Number of Burn-in Steps: %i"
                      % (np.round(tau), burnin_step))
## WPBWPB: need to clean this up eventually (don't hard code numderpar)
        if self.dust_em_class.fixed: 
            numderpar = 3
        else: 
            if self.dust_em_class.assume_energy_balance:
                numderpar = 5
            else:
                numderpar = 4
        new_chain = np.zeros((self.nwalkers, self.nsteps, ndim+numderpar+1))
        new_chain[:, :, :-(numderpar+1)] = sampler.chain
        self.chain = sampler.chain
        for i in xrange(len(sampler.blobs)):
            for j in xrange(len(sampler.blobs[0])):
                for k in xrange(len(sampler.blobs[0][0])):
                    x = sampler.blobs[i][j][k]
                    if k==0 or k==4: #Stellar mass or Dust mass--can't take log of negative numbers; also, want reasonable values
                        new_chain[j, i, -(numderpar+1)+k] = np.where((np.isfinite(x)) * (x > 10.),
                                               np.log10(x), -99.) #Stellar mass and dust mass (energy balance version)
                    else: 
                        new_chain[j, i, -(numderpar+1)+k] = np.where((np.isfinite(x)),np.log10(x), -99.) #Other derived params
        new_chain[:, :, -1] = sampler.lnprobability
        self.samples = new_chain[:, burnin_step:, :].reshape((-1, ndim+numderpar+1))


    def get_derived_params(self):
        ''' These are not free parameters in the model, but are instead
        calculated from free parameters
        '''
        ageval = 10**self.sfh_class.age #Age in Gyr
        t_sfr100 = np.linspace(1.0e-9,0.1,num=251) #From 100 Mya to present (observed time); avoid t=0 for log purposes
        t_sfr10 = np.linspace(1.0e-9,0.01,num=251) #From 10 Mya to present (observed time); avoid t=0 for log purposes
        sfrarray = self.sfh_class.evaluate(t_sfr100)
        sfr100 = simps(sfrarray,x=t_sfr100)/(t_sfr100[-1]-t_sfr100[0]) #Mean value over last 100 My
        sfrarray = self.sfh_class.evaluate(t_sfr10)
        sfr10 = simps(sfrarray,x=t_sfr10)/(t_sfr10[-1]-t_sfr10[0]) #Mean value over last 10 My

        if self.dust_em_class.fixed:
            fpdr = None
        else:
            if self.dust_em_class.assume_energy_balance:
                umin,gamma,qpah = self.dust_em_class.get_params()
            else:
                umin,gamma,qpah,mdust = self.dust_em_class.get_params()
            umax = 1.0e6
            fpdr = gamma*np.log(umax/100.) / ((1.-gamma)*(1.-umin/umax) + gamma*np.log(umax/umin))

        return sfr10,sfr100,fpdr


    def set_median_fit(self,rndsamples=200,lnprobcut=7.5):
        '''
        set attributes
        median spectrum and filter flux densities for rndsamples random samples

        Input
        -----
        rndsamples : int
            number of random samples over which to compute medians
        lnprobcut : float
            Some of the emcee chains include outliers.  This value serves as
            a cut in log probability space with respect to the maximum
            probability.  For reference, a Gaussian 1-sigma is 2.5 in log prob
            space.

        Returns
        -------
        self.fluxwv : list (1d)
            wavelengths of filters
        self.fluxfn : list (1d)
            median flux densities of filters
        self.medianspec : list (1d)
            median spectrum
        '''
        chi2sel = (self.samples[:, -1] >
                   (np.max(self.samples[:, -1], axis=0) - lnprobcut))
        nsamples = self.samples[chi2sel, :]
        wv = self.get_filter_wavelengths()
        sp, fn = ([], [])
        for i in np.arange(rndsamples):
            ind = np.random.randint(0, nsamples.shape[0])
            self.set_class_parameters(nsamples[ind, :])
            if self.dust_em_class.assume_energy_balance:
                self.spectrum, mass, mdust_eb = self.build_csp()
            else:
                self.spectrum, mass = self.build_csp()
            fnu = self.get_filter_fluxdensities()
            sp.append(self.spectrum * 1.)
            fn.append(fnu * 1.)
        self.medianspec = np.median(np.array(sp), axis=0)
        self.fluxwv = wv
        self.fluxfn = np.median(np.array(fn), axis=0)


    def spectrum_plot(self, ax, color=[0.996, 0.702, 0.031], alpha=0.1):
        ''' Make spectum plot for current model '''
        if self.dust_em_class.assume_energy_balance:
            self.spectrum, mass, mdust_eb = self.build_csp()
        else:
            self.spectrum, mass = self.build_csp()
        self.true_spectrum = self.spectrum.copy()
        ax.plot(self.wave, self.spectrum, color=color, alpha=alpha)

    def add_sfr_plot(self, ax1):
        ax1.set_xscale('log')
        ax1.set_yscale('log')
        ax1.set_ylabel(r'SFR [$M_{\odot} yr^{-1}$]')
        ax1.set_xlabel('Lookback Time') 
        ax1.set_xticks([1e-3, 1e-2, 1e-1, 1])
        ax1.set_xticklabels(['1 Myr', '10 Myr', '100 Myr', '1 Gyr'])
        ax1.set_yticks([1e-2, 1e-1, 1, 1e1, 1e2, 1e3])
        ax1.set_yticklabels(['0.01', '0.1', '1', '10', '100', '1000'])
#        ax1.set_yticks([1e-2, 1, 1e1, 1e3])
#        ax1.set_yticklabels(['0.01', '1', '10', '1000'])
        ax1.set_xlim([10**-3, max(10**self.sfh_class.age, 1.02)])
        ax1.set_ylim([10**-2.3, 1e3])
        ax1.minorticks_on()

    def add_dust_plot(self, ax2):
        ax2.set_xscale('log')
        xtick_pos = [2000, 4000, 8000]
        xtick_lbl = ['2000', '4000', '8000']
        ax2.set_xticks(xtick_pos)
        ax2.set_xticklabels(xtick_lbl)
        ax2.set_xlim([1000, 10000])
        ax2.set_ylim([0.01, 4])
#        ax2.set_ylabel(r'Dust Attenuation (mag)')
        ax2.set_ylabel(r'$A_\lambda$ [mag]')
        ax2.set_xlabel(r'Wavelength [$\AA$]')

    def add_spec_plot(self, ax3):
# WPBWPB: adjust wavelength range, depending on whether dust emission is fit
        ax3.set_xscale('log')
        if self.dust_em_class.fixed:
            xtick_pos = [1000, 3000, 5000, 10000, 20000, 40000]
            xtick_lbl = ['0.1', '0.3', '0.5', '1', '2', '4']
# WPBWPB delete
#            xlims = [3000, 50000]
            xlims = (1. + self.redshift) * np.array([1150, 20000])
            xlims[0] = min( xlims[0], min(self.fluxwv) - 200)
            xlims[1] = max( xlims[1], max(self.fluxwv) + 5000) 
        else:
            xtick_pos = [3000, 5000, 10000, 40000, 100000, 400000, 1000000]
            xtick_lbl = ['0.3', '0.5', '1', '4', '10', '40', '100']
# WPBWPB delete
#            xlims = [3000, 2000000]
            xlims = (1. + self.redshift) * np.array([1150, 700000])
            xlims[0] = min( xlims[0], min(self.fluxwv) - 200)
            xlims[1] = max( xlims[1], max(self.fluxwv) + 50000) 
            ax3.set_yscale('log')
        ax3.set_xticks(xtick_pos)
        ax3.set_xticklabels(xtick_lbl)
        ax3.set_xlim(xlims)
        ax3.set_xlabel(r'Wavelength [$\mu$m]')
        ax3.set_ylabel(r'$F_{\nu}$ [$\mu$Jy]')

    def add_subplots(self, ax1, ax2, ax3, nsamples, rndsamples=200):
        ''' Add Subplots to Triangle plot below '''
### WPBWPB -- I think all of this can be deleted - migrated to a separate method that does not require plotting (double-commented lines within this method)
##        wv = self.get_filter_wavelengths()
##        rndsamples = 200
        sp, fn = ([], []) 
        for i in np.arange(rndsamples):
            ind = np.random.randint(0, nsamples.shape[0])
            self.set_class_parameters(nsamples[ind, :])
            self.sfh_class.plot(ax1, alpha=0.1)
            self.dust_abs_class.plot(ax2, self.wave, alpha=0.1)
            self.spectrum_plot(ax3, alpha=0.1)

##            fnu = self.get_filter_fluxdensities()
##            sp.append(self.spectrum * 1.)
##            fn.append(fnu * 1.)
## WPB edit: plotting HBeta line
## used to have self.hbflux = self.measure_hb() --> changed
##            hbm.append(self.hbflux * 1.)
##        # Plotting median value:
##        self.medianspec = np.median(np.array(sp), axis=0)
###        self.hbmedian = np.median(hbm)
        ax3.plot(self.wave, self.medianspec, color='dimgray')
##        self.fluxwv = wv
##        self.fluxfn = np.median(np.array(fn), axis=0)

        ax3.scatter(self.fluxwv, self.fluxfn, marker='x', s=200,
                    color='dimgray', zorder=8)
        if self.input_params is not None:
            self.set_class_parameters(self.input_params)
            self.sfh_class.plot(ax1, color='k', alpha=1.0)
            self.dust_abs_class.plot(ax2, self.wave, color='k', alpha=1.0)
            self.spectrum_plot(ax3, color='k', alpha=0.5)
        if self.true_fnu is not None:
            p = ax3.scatter(self.fluxwv, self.true_fnu, marker='o', s=150,
                            color=[0.216, 0.471, 0.749], zorder=9)
            p.set_facecolor('none')
        ax3.errorbar(self.fluxwv, self.data_fnu, yerr=self.data_fnu_e, fmt='s',
                     fillstyle='none', markersize=150,
                     color=[0.510, 0.373, 0.529], zorder=10)
        ax3.scatter(self.fluxwv, self.data_fnu, marker='s', s=150,facecolors='none',
                    edgecolors=[0.510, 0.373, 0.529], linewidths=2, zorder=10)        
        sel = np.where((self.fluxwv > ax3.get_xlim()[0]) * (self.fluxwv < ax3.get_xlim()[1]))[0]
        ax3min = np.percentile(self.data_fnu[sel][self.data_fnu[sel]>0.0], 1)
        ax3max = np.percentile(self.data_fnu[sel][self.data_fnu[sel]>0.0], 99)
        ax3ran = ax3max - ax3min
        if not self.dust_em_class.fixed: 
            ax3max = max(max(self.data_fnu),max(self.medianspec))
            ax3.set_ylim([ax3min*0.5, ax3max + 0.4 * ax3ran])
            ax3.set_xlim(right=max(max(self.fluxwv),max(self.wave)))
        else:
            ax3.set_ylim([ax3min - 0.4 * ax3ran, ax3max + 0.6 * ax3ran])
        ax3.text((1.+self.redshift)*1400, ax3max,
                 r'${\chi}_{\nu}^2 = $%0.2f' % self.chi2['rchi2'])


    def triangle_plot(self, outname, lnprobcut=7.5, imgtype='png'):
        ''' Make a triangle corner plot for samples from fit

        Input
        -----
        outname : string
            The triangle plot will be saved as "triangle_{outname}.png"
        lnprobcut : float
            Some of the emcee chains include outliers.  This value serves as
            a cut in log probability space with respect to the maximum
            probability.  For reference, a Gaussian 1-sigma is 2.5 in log prob
            space.
        imgtype : string
            The file extension of the output plot
        '''
# WPBWPB: since median fits have already been set, may be able to remove lnprobcut -- just use attributes that are already set.
        # Make selection for three sigma sample
        chi2sel = (self.samples[:, -1] >
                   (np.max(self.samples[:, -1], axis=0) - lnprobcut))
        nsamples = self.samples[chi2sel, :]
# WPBWPB: understand this line....
        o = 0  # self.sfh_class.nparams
        names = self.get_param_names()[o:]
        names.append('Log Mass')
        if self.dust_em_class.assume_energy_balance:
            names.append("Log Dust Mass")
        if self.input_params is not None:
            truths = self.input_params[o:]
        else:
            truths = None
        percentilerange = [p for i, p in enumerate(self.get_param_lims())
                           if i >= o] + [[7, 11]]
        percentilerange = [.95] * len(names)
        if self.dust_em_class.fixed: 
            numderpar = 3
        else: 
            if self.dust_em_class.assume_energy_balance:
                numderpar = 5
            else:
                numderpar = 4
        start = time.time()
        if self.dust_em_class.assume_energy_balance:
            indarr = np.concatenate((np.arange(o,len(nsamples[0])-numderpar),np.array([-2]))) #Want to include dust mass and stellar mass as well as all free parameters in triangle plot
        else:
            indarr = np.arange(o,len(nsamples[0])-numderpar) #Want to include stellar mass and all free parameters (this time including dust mass) in triangle plot
        fsgrad = 11+int(round(0.75*len(indarr)))
        fig = corner.corner(nsamples[:, indarr], labels=names,
                            range=percentilerange,
                            truths=truths, truth_color='gainsboro',
                            label_kwargs={"fontsize": fsgrad}, show_titles=True,
                            title_kwargs={"fontsize": fsgrad-2},
                            quantiles=[0.16, 0.5, 0.84], bins=30)
        w = fig.get_figwidth()
        fig.set_figwidth(w-(len(indarr)-13)*0.025*w)
        end = time.time()
        print('made the corner. it took me %s s' % (end - start))

        # Adding subplots
        w = fig.get_figwidth()
        fig.set_figwidth(w-(len(indarr)-13)*0.025*w)
        ax1 = fig.add_subplot(3, 1, 1)
        ax1.set_position([0.7-0.02*(len(indarr)-5), 0.60+0.001*(len(indarr)-5), 0.28+0.02*(len(indarr)-5), 0.15+0.001*(len(indarr)-5)])
        ax2 = fig.add_subplot(3, 1, 2)
        ax2.set_position([0.7+0.008*(15-len(indarr)), 0.39, 0.28-0.008*(15-len(indarr)), 0.15])
        ax3 = fig.add_subplot(3, 1, 3)
        ax3.set_position([0.38-0.008*(len(indarr)-4), 0.82-0.001*(len(indarr)-4), 0.60+0.008*(len(indarr)-4), 0.15+0.001*(len(indarr)-4)])
        self.add_sfr_plot(ax1)
# WPBWPB delete:
#        print("I've added the sfr plot")
        self.add_dust_plot(ax2)
# WPBWPB delete:
#        print("I've added the dust plot")
        self.add_spec_plot(ax3)
# WPBWPB delete:
#        print("I've added the spec plot")
        self.add_subplots(ax1, ax2, ax3, nsamples)
# WPBWPB delete:
#        print("I've added the subplots")
# WPB edit: printing HBeta line flux on the figure
# used to have self.hbflux = self.measure_hb() --> changed
#        if self.sfh_class.hblim is not None:
#            fig.text(.5, .75, r'H$\beta$ input: %0.2f' %
#                     (self.sfh_class.hblim * 1e17), fontsize=18)
#        fig.text(.5, .70, r'H$\beta$ model: %0.2f' % (self.hbmedian * 1e17),
#                 fontsize=18)
        # fig.set_size_inches(15.0, 15.0)

        for ax_loc in fig.axes:
            ax_loc.minorticks_on() 
            ax_loc.set_axisbelow('False')

        fig.savefig("%s.%s" % (outname, imgtype), dpi=150)
        plt.close(fig)
        end = time.time()
        print("Time taken to make triangle plot: %.3f s"%(end-start))

    def sample_plot(self, outname, imgtype='png'):
        ''' Make a sample plot

        Input
        -----
        outname : string
            The sample plot will be saved as "sample_{outname}.png"
        imgtype : string
            The file extension of the output plot

        '''
        # Make selection for three sigma sample
        names = self.get_param_names()
        if self.input_params is not None:
            truths = self.input_params
        else:
            truths = None
        fig, ax = plt.subplots(self.chain.shape[2], 1, sharex=True,
                               figsize=(5, 2*self.chain.shape[2]))
        for i, a in enumerate(ax):
            for chain in self.chain[:, :, i]:
                a.plot(chain, 'k-', alpha=0.3)
            a.set_ylabel(names[i])
            if truths is not None:
                a.plot([0, self.chain.shape[1]], [truths[i], truths[i]], 'r--')
            if i == len(ax)-1:
                a.set_xlabel("Step")

        for ax_loc in fig.axes:
            ax_loc.minorticks_on()

        fig.savefig("%s.%s" % (outname, imgtype))
        plt.tight_layout()
        plt.close(fig)

    def add_fitinfo_to_table(self, percentiles, start_value=3, lnprobcut=7.5,
                             numsamples=1000):
        ''' Assumes that "Ln Prob" is the last column in self.samples'''
        chi2sel = (self.samples[:, -1] >
                   (np.max(self.samples[:, -1], axis=0) - lnprobcut))
        nsamples = self.samples[chi2sel, :-1]
        n = len(percentiles)
        for i, per in enumerate(percentiles):
            for j, v in enumerate(np.percentile(nsamples, per, axis=0)):
                self.table[-1][(i + start_value + j*n)] = v
        return (i + start_value + j*n)

    def add_truth_to_table(self, truth, start_value):
        for i, tr in enumerate(truth):
            self.table[-1][start_value + i + 1] = tr

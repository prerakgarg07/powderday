import random
import numpy as np
import pfh_readsnap
import parameters as par
from datetime import datetime
from astropy.table import Table
from astropy.io import ascii
import constants as const
import pdb
import sys

import scipy.interpolate
import scipy.ndimage

import fsps 
from multiprocessing import Pool



class Stars:
    def __init__(self,mass,metals,positions,age):
        self.mass = mass
        self.metals = metals
        self.positions = positions
        self.age = age
    def info(self):
        return(self.mass,self.metals,self.positions,self.age)



def allstars_sed_gen():


    #NOTE this part is just for the gadget simulations - this will
    #eventually become obviated as it gets passed into a function to
    #populate the stars_list with objects as we start to feed in new
    #types of simulation results.

    print 'reading in stars particles for SPS calculation'

    sdir = par.hydro_dir
    snum = par.Gadget_snap_num

    #NEW STARS
    new_stars_dict = pfh_readsnap.readsnap(sdir,snum,4)
    mass = new_stars_dict['m']*par.unit_mass*const.msun #g (as par.unit_mass is in msun)
    metals = new_stars_dict['z']
    positions = new_stars_dict['p']*par.unit_length*const.pc*1.e3 #cm (as par.unit_length is kpc)
    age = new_stars_dict['age'] #Gyr (per phopkins)

    median_metallicity = np.median(metals)
  
    nstars = len(age)
    print 'number of new stars =',nstars
    

    #create the stars_list full of Stars objects
    stars_list = []
    for i in range(nstars):
        stars_list.append(Stars(mass[i],metals[i],positions[i],age[i]))

  


    print 'generating stellar SEDs'


    '''
    #first figure out how many wavelengths there are
    sp = fsps.StellarPopulation(tage=age[0],imf_type=1,sfh=0)
    spec = sp.get_spectrum(tage=age[0])
    nu = 1.e8*const.c/spec[0]
    fnu = spec[1]

    nlam = len(nu)

    stellar_nu = np.zeros([nlam])
    stellar_fnu = np.zeros([nstars,nlam])
    
    disk_fnu = np.zeros(nlam)
    bulge_fnu = np.zeros(nlam)
    
    #DEBUG DEBUG DEBUG 
    #for now we don't have a metallicity in the sps calculations
    print '========================='
    print 'WARNING: METALLICITIES NOT ACCOUNTED FOR IN STELLAR SEDS'
    print '========================'
    
    newstars_gen(age)

    #calculate the SEDs for new stars
    for i in range(nstars):
        
        sp = fsps.StellarPopulation(tage=age[i],imf_type=1,sfh=0)
        spec = sp.get_spectrum(tage=age[i])

        stellar_nu[:] = 1.e8*const.c/spec[0]
        stellar_fnu[i,:] = spec[1]


    '''

    stellar_nu,stellar_fnu = newstars_gen(stars_list)
    
        
    if par.COSMOFLAG == False: 

        #DISK STARS
        disk_stars_dict = pfh_readsnap.readsnap(sdir,snum,2)
        nstars_disk = len(disk_stars_dict['m'])
        disk_positions = disk_stars_dict['p']*par.unit_length*const.pc*1.e3 #cm (as par.unit_length is kpc)
        disk_masses = disk_stars_dict['m']*par.unit_mass*const.msun #g (as par.unit_mass is in msun)
    
        #BULGE STARS
        bulge_stars_dict = pfh_readsnap.readsnap(sdir,snum,3)
        nstars_bulge = len(bulge_stars_dict['m'])
        bulge_positions = bulge_stars_dict['p']*par.unit_length*const.pc*1.e3 #cm (as par.unit_length is kpc)
        bulge_masses = bulge_stars_dict['m']*par.unit_mass*const.msun #g (as par.unit_mass is in msun)
        
    else: 
        #we just assign bogus values to the disk and bulge masses: equate them to the newstar values
        disk_masses = mass
        disk_fnu = stellar_fnu
        bulge_masses = mass
        bulge_fnu = fnu



    #calculate the SED for disk stars

    sp = fsps.StellarPopulation(tage = par.disk_stars_age,imf_type=1,sfh=0)
    spec = sp.get_spectrum(tage=par.disk_stars_age)
    disk_fnu = spec[1]

    #calculate the SED for bulge stars
    sp = fsps.StellarPopulation(tage = par.bulge_stars_age,imf_type=1,sfh=0)
    spec = sp.get_spectrum(tage=par.bulge_stars_age)
    bulge_fnu = spec[1]
    

    

    return positions,disk_positions,bulge_positions,mass,stellar_nu,stellar_fnu,disk_masses,disk_fnu,bulge_masses,bulge_fnu



def newstars_gen(stars_list):
    #the newstars (particle type 4; so, for cosmological runs, this is all
    #stars) are calculated in a separate function with just one argument so that it is can be fed 
    #into pool.map for multithreading.
    

    


    #first figure out how many wavelengths there are
    sp = fsps.StellarPopulation(tage=stars_list[0].age,imf_type=1,sfh=0)
    spec = sp.get_spectrum(tage=stars_list[0].age)
    nu = 1.e8*const.c/spec[0]
    fnu = spec[1]

    nlam = len(nu)

    stellar_nu = np.zeros([nlam])
    stellar_fnu = np.zeros([len(stars_list),nlam])
    
  
    
    #DEBUG DEBUG DEBUG 
    #for now we don't have a metallicity in the sps calculations
    print '========================='
    print 'WARNING: METALLICITIES NOT ACCOUNTED FOR IN STELLAR SEDS'
    print '========================'
    
    

    #calculate the SEDs for new stars
    for i in range(len(stars_list)):
        
        sp = fsps.StellarPopulation(tage=stars_list[i].age,imf_type=1,sfh=0)
        spec = sp.get_spectrum(tage=stars_list[i].age)

        stellar_nu[:] = 1.e8*const.c/spec[0]
        stellar_fnu[i,:] = spec[1]

    return stellar_nu,stellar_fnu

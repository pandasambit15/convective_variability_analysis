"""
This is a script to analyze the convetive variance from 
COSMO ensembles
"""
# Imports
import sys
from cosmo_utils.pyncdf import getfobj_ncdf_ens, getfobj_ncdf
from cosmo_utils.diag import mean_spread_fieldobjlist, identify_clouds, rdf
from cosmo_utils.plot import fig_contourf_1sp, ax_contourf
from cosmo_utils.helpers import yyyymmddhh_strtotime, make_timelist, ddhhmmss, yyyymmddhh
from datetime import timedelta
import os
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
from scipy.ndimage import measurements
import copy
from scipy.optimize import leastsq
np.seterr(divide='ignore', invalid='ignore')   # Suppress invalide divide warnings

def origin_residual(p, x, y):
    slope = p
    err = y - (slope * x)
    return err


# Plot settings
mpl.rcParams['font.size'] = 10
mpl.rcParams['font.family'] = 'sans-serif'
mpl.rcParams['lines.linewidth'] = 1.5
mpl.rcParams['legend.fontsize'] = 8


cmTAUC = ("#FFFFC1","#FDFEB3","#FCF6A5","#FCEF97","#FCE88A","#FCE07E",
          "#FCD873","#FCD068","#FCC860","#FCC058","#FCB853","#FBB04F",
          "#FAA74E","#F89F4E","#F7964F","#F58E52","#F28655","#F07D59",
          "#ED745D","#E96C61","#E66365","#E25A6A","#DE516D","#D94771",
          "#D53D74","#D03178","#CB247B","#C6117D","#C10080","#BC0083",
         )
levelsTAUC = np.arange(0, 31, 1)

cmNVAR = ("#0030C4","#3F5BB6","#7380C0","#A0A7CE","#CCCEDC","#DDCACD",
          "#D09AA4","#BF6A7D","#AA3656","#920031")

levelsNVAR = [1, 1.14, 1.33, 1.6, 1.78, 2, 2.25, 2.5, 3, 3.5, 4]

cmMP = ("#DBA9B4","#DDA6A0","#D8A786","#CAAA68","#B1AF4C","#8DB340",
          "#50B750","#00B76E","#00B28C","#007678")
levelsMP = np.linspace(0,1+1/11,11)

# Clist for n
clist = ("#ff0000", "#ff8000", "#e6e600","#40ff00","#00ffff","#0040ff","#ff00ff")



# Setup
plotlist = ['all']   # not plottling saves a significant amount of time
collapse = True
ana = sys.argv[1]  # 'm' or 'p'
date = sys.argv[2]
water = True
try: 
    if sys.argv[3] == 'nowater':
        water = False
except:
    pass
ensdir = '/home/scratch/users/stephan.rasp/' + date + '/deout_ceu_pspens/'
nens = 20
tstart = timedelta(hours=8)   # Cannot be 0 because of tau_c calculation!
tend = timedelta(hours = 20)  
# temporal resolution for analysis (30 min is possible)
tinc = timedelta(hours = 1)


plotdir = '/home/s/S.Rasp/Dropbox/figures/PhD/variance/' + date + '/' + ana
if not collapse:
    plotdir += '_noncollapse'
    date = 'noncoll_' + date
if not water:
    plotdir += '_nowater'
    date = 'nowater_' + date
plotdir += '/'
dx = 2800.


nlist = [256, 128, 64, 32, 16, 8, 4]

# Specific setup for type of analysis
if ana == 'm':
    # Vertical analysis levels 
    #hlist = [500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 5000, 6000, 7000,
             #8000, 9000, 10000]
    hlist = [3000]
    # Load HH file
    HH = getfobj_ncdf(ensdir + '/1/OUTPUT/lfff00000000c.nc_30m', 'HHL')
    aslcol = HH.data[:, -1, -1]   # ATTENTION Hard coded colums above sea level 
    levlist = []
    realhlist = []
    for h in hlist:
        levlist.append(np.argmin(np.abs(aslcol-h)))   # find closest level
        realhlist.append(aslcol[np.argmin(np.abs(aslcol-h))])
        
    fieldn = 'W'
    thresh = 1.
    sufx = '.nc_30m'
    ana_unit = 'kg/s'
    cmWP = ("#7C0607","#903334","#A45657","#BA7B7C","#FFFFFF",
        "#8688BA","#6567AA","#46499F","#1F28A2")
    levelsWP = [-5, -4, -3, -2, -1, 1, 2, 3, 4, 5]
    sizemax = 2e8
    summax = 7.5e8

if ana == 'p':
    levlist = [None]
    realhlist = ['surf']
    fieldn = 'TOT_PR'
    thresh = 0.001
    sufx = '.nc_30m_surf'
    ana_unit = 'mm/h'
    cmWP = ((1    , 1     , 1    ), 
            (0    , 0.627 , 1    ),
            (0.137, 0.235 , 0.98 ),
            (0.392, 0     , 0.627),
            (0.784, 0     , 0.627),
            (1    , 0.3   , 0.9  ) )
            #(0.1  , 0.1   , 0.784),
    levelsWP = [0, 0.001, 0.003, 0.01, 0.03, 0.1, 0.3]
    sizemax = 10.e8
    summax = 1
    
# Create plotdir if not exist
if not os.path.exists(plotdir): os.makedirs(plotdir)

# Loop over levs:
for lev, realh in zip(levlist, realhlist):
    print 'lev:', lev
    print 'real h:', realh
    levstr = 'lev = ' + str(lev)
    realhstr = 'height asl = ' + str(realh)


    # Make the timelist
    timelist = make_timelist(tstart, tend, tinc)
    # Time loop 

    # Initialize time lists
    r_cluster_list = []
    r_cdf_cluster_list = []
    sizemmean_list = []
    summean_list = []
    total_list = []
    dimeantauc_list = []

    nvar_n_list = []
    var_n_over_n = []
    adj_nvar_n_list = []
    for i in range(len(nlist)):
        nvar_n_list.append([])
        var_n_over_n.append([])
        adj_nvar_n_list.append([])

    # Initialize total lists for correlation
    var_alllist = []
    M_alllist = []
    m_alllist = []
    N_alllist = []
    n_alllist = []
    tauc_alllist = []
    UTC_alllist = []

    for t in timelist:
        print t
        
        ncdffn = 'lfff' + ddhhmmss(t) + sufx
        
        # Load ensembles 
        fobjlist = getfobj_ncdf_ens(ensdir, 'sub', nens, ncdffn, 
                                    dir_suffix='/OUTPUT/',
                                    fieldn = fieldn, nfill=1, levs = lev)
        if ana == 'm':   # Additional positive QC filter
            qcobjlist = getfobj_ncdf_ens(ensdir, 'sub', nens, ncdffn, 
                                        dir_suffix='/OUTPUT/',
                                        fieldn = 'QC', nfill=1, levs = lev)
            ncdffn_rho = ncdffn + '_buoy'
            rhoobjlist = getfobj_ncdf_ens(ensdir, 'sub', nens, ncdffn_rho, 
                                        dir_suffix='/OUTPUT/',
                                        fieldn = 'RHO', nfill=1, levs = lev)
        else:
            qcobjlist = [None]*len(fobjlist)
            rhoobjlist = [None]*len(fobjlist)
        
        # Evaluate the 256x256 analysis domain
        sxo, syo = fobjlist[0].data.shape  # Original field shape
        lx1 = (sxo-256-1)/2 # ATTENTION first dimension is actually y
        lx2 = -(lx1+1) # Number of grid pts to exclude at border
        ly1 = (syo-256-1)/2
        ly2 = -(ly1+1)

        
        
        # Calculate what needs to be calculated
        # 1. Tau_c
        taucfn = 'lfff' + ddhhmmss(t) + '.nc_30m_surf'
        tauclist = getfobj_ncdf_ens(ensdir, 'sub', nens, taucfn, 
                                    dir_suffix='/OUTPUT/',
                                    fieldn = 'TAU_C', nfill=1)
        # Get mean tauc object
        meantauc, tmp = mean_spread_fieldobjlist(tauclist, nan = True)
        dimeantauc = np.nanmean(meantauc.data[lx1:lx2, ly1:ly2])
        dimeantauc_list.append(dimeantauc)
        
        # Loop over members 
        sizelist = []
        sumlist = []
        glist = []
        
        # For n loop
        comlist = []
        labelslist = []
        for fobj, qcobj, rhoobj in zip(fobjlist, qcobjlist, rhoobjlist):
            # 2. Cloud size and m/p distribution
            if ana == 'm':
                #field = fobj.data[0,lx1:lx2, ly1:ly2]
                field = fobj.data[lx1:lx2, ly1:ly2]
                labels, cld_size, cld_sum = identify_clouds(field,
                                                            thresh , 
                                                            #qcobj.data[0,lx1:lx2, ly1:ly2],
                                                            qcobj.data[lx1:lx2, ly1:ly2],
                                                            opt_thresh = 0.,
                                                            water = water,
                                                            rho = rhoobj.data[lx1:lx2, ly1:ly2])
                
                cld_sum *= dx*dx  # Rho is now already included
            else:
                field = fobj.data[lx1:lx2, ly1:ly2]
                labels, cld_size, cld_sum = identify_clouds(field,
                                                            thresh = thresh)
            sizelist.append(cld_size)
            sumlist.append(cld_sum) 
                    
            # 3. Calculate RDF
            g, r = rdf(labels, field, normalize = True, rmax = 30, dr = 2)
            glist.append(g)
            
            labelslist.append(labels)
            
            # 4. Calculate Variance (Save for n loop below)
            # TODO: Put this into a function later on
            num = np.unique(labels).shape[0]   # Number of clouds
            # Get center of mass for each cluster
            com = np.array(measurements.center_of_mass(field, labels, range(1,num)))
            if com.shape[0] == 0:   # Accout for empty arrays
                com = np.empty((0,2))
            comlist.append(com)
            sx, sy = field.shape
            
            
        # cont 2. Calculate histograms
        sizelist_flat = [i for sl in sizelist for i in sl]
        sumlist_flat = [i for sl in sumlist for i in sl]
        sizehist, sizeedges = np.histogram(sizelist_flat, 
                                        bins = 15, range = [0., sizemax])
        sumhist, sumedges = np.histogram(sumlist_flat, 
                                        bins = 15, range = [0., summax])
        sizemean = np.mean(sizelist_flat)
        summean = np.mean(sumlist_flat)
        total = np.sum(sumlist_flat)
        sizemmean_list.append(sizemean)
        summean_list.append(summean)
        total_list.append(total)
        
        
        # cont 3. Get means after member loop
        #print glist
        g = np.mean(glist, axis = 0)
        # Get clustering radius
        gthresh = 1.0
        # convert to CDF
        # Integrate g
        g_cdf = np.cumsum(g)/(g.shape[0]-1)
        g_cdf_thresh = 0.5
        
        if not np.isnan(np.mean(g)):
            # This is the index where g drops below one after the first peak
            tmpwhere = np.where(g < gthresh)[0]
            if tmpwhere[0] == 0:   # First point is below zero
                gind = tmpwhere[np.where(np.diff(tmpwhere) > 1)[0][0]+1]
            else:
                gind = tmpwhere[0]
            r_cluster = r[gind]/1000.   # In km
            
            # get radius from CDF 
            r_cdf_cluster = r[np.where(g_cdf > g_cdf_thresh)[0][0]]/1000.

        else:
            r_cluster = np.nan
            r_cdf_cluster = np.nan
        r_cluster_list.append(r_cluster)
        r_cdf_cluster_list.append(r_cdf_cluster)
        
        # cont 4. Variance
        # Loop over n
        varres1list = []
        varres2list = []
        
        for i_n, n in enumerate(nlist):
            print 'n', n
            # Determine size of coarse arrays
            nx = int(np.floor(sx/n))
            ny = int(np.floor(sy/n))
            
            # Allocate ens lists
            mplist = []
            MPlist = []
            Nlist = []
            
            # Loop over members
            for fobj, labels, com, cld_sum in zip(fobjlist, labelslist, comlist, 
                                                sumlist):
                #if ana == 'm':
                    #field = fobj.data[0,lx1:lx2, ly1:ly2]
                #else: 
                field = fobj.data[lx1:lx2, ly1:ly2]
            
                # Allocate array for saving
                mp_field = np.empty((nx, ny))
                MP_field = np.empty((nx, ny))
                N_field = np.empty((nx, ny))
                # Loop over "coarse" array
                for i in range(nx):
                    for j in range(ny):
                        # Get limits for each N box
                        xmin = i*n
                        xmax = (i+1)*n
                        ymin = j*n
                        ymax = (j+1)*n
                        
                        if collapse:
                            # 1. The collapsed version
                            # Create bool_arr
                            bool_arr = ((com[:,0]>=xmin)&(com[:,0]<xmax)&
                                        (com[:,1]>=ymin)&(com[:,1]<ymax))
                            # Get cld_size for subdomain
                            sub_cld_sum = cld_sum[bool_arr]
                            
                        
                        else:
                            # 2. The "normal version"
                            subfield = field[i*n:(i+1)*n, j*n:(j+1)*n]
                            sublabels = labels[i*n:(i+1)*n, j*n:(j+1)*n]
                            lrange = np.unique(sublabels)
                            sub_cld_sum = measurements.sum(subfield, sublabels,
                                                        lrange[1:])*dx*dx*0.9575
                            
                        # Get important values
                        mp_field[i, j] = np.mean(sub_cld_sum)
                        MP_field[i, j] = np.sum(sub_cld_sum)
                        N_field[i, j] = sub_cld_sum.shape[0]
                            
                
                # Write into ensemble list
                mplist.append(mp_field)
                MPlist.append(MP_field)
                Nlist.append(N_field)
                
            # Upscale tau
            tauc_orig = meantauc.data[lx1:lx2, ly1:ly2]
            tauc_field = np.empty((nx, ny))
            for i in range(nx):
                for j in range(ny):
                    tauc_field[i, j] = np.nanmean(tauc_orig[i*n:(i+1)*n, j*n:(j+1)*n])
                
            # Calculate ensemble means and variances, fields
            var = np.var(MPlist, axis = 0, ddof = 1)
            MPmean = np.mean(MPlist, axis = 0)
            mpmean = np.nanmean(mplist, axis = 0)
            Nmean = np.mean(Nlist, axis = 0)
            Nvar = np.var(Nlist, axis = 0, ddof = 1)
            
            # Append to alllist
            var_alllist += list(np.ravel(var))
            M_alllist += list(np.ravel(MPmean))
            m_alllist += list(np.ravel(mpmean))
            N_alllist += list(np.ravel(Nmean))
            tauc_alllist += list(np.ravel(tauc_field))
            n_alllist += [n]*len(list(np.ravel(var)))
            UTC_alllist += [t]*len(list(np.ravel(var)))
            
            # Plot these fields now
            # First, have to upscale them again to the model grid
            var_fullfield = np.ones((fobj.ny, fobj.nx)) * np.nan
            MP_fullfield = np.ones((fobj.ny, fobj.nx)) * np.nan
            mp_fullfield = np.ones((fobj.ny, fobj.nx)) * np.nan
            for i in range(nx):
                for j in range(ny):
                    # Get limits for each N box
                    xmin = i*n+lx1
                    xmax = (i+1)*n+lx1
                    ymin = j*n+ly1
                    ymax = (j+1)*n+ly1
                    
                    var_fullfield[xmin:xmax, ymin:ymax] = var[i,j]
                    MP_fullfield[xmin:xmax, ymin:ymax] = MPmean[i,j]
                    mp_fullfield[xmin:xmax, ymin:ymax] = mpmean[i,j]
            
            # Create new fobj
            var_fobj = copy.deepcopy(fobj)
            var_fobj.data = var_fullfield
            var_fobj.dims = 2
            var_fobj.fieldn = 'Var'
            var_fobj.unit = '(' + ana_unit + ')^2'
            
            MP_fobj = copy.deepcopy(fobj)
            MP_fobj.data = MP_fullfield
            MP_fobj.data[MP_fobj.data == 0] = np.nan
            MP_fobj.dims = 2
            MP_fobj.unit = ana_unit
            
            mp_fobj = copy.deepcopy(fobj)
            mp_fobj.data = mp_fullfield
            mp_fobj.data[mp_fobj.data == 0] = np.nan
            mp_fobj.dims = 2
            mp_fobj.unit = ana_unit
            
            nvar_n_fobj = copy.deepcopy(fobj)
            nvar_n_fobj.data = var_fullfield /MP_fullfield/mp_fullfield
            nvar_n_fobj.dims = 2
            nvar_n_fobj.unit = ''
            
            if ana == 'm':
                MP_fobj.fieldn = 'M'
                mp_fobj.fieldn = 'm'
                nvar_n_fobj.fieldn = 'Normalized Var * N'
                mpmax = 2e8
            else:
                MP_fobj.fieldn = 'P'
                mp_fobj.fieldn = 'p'
                nvar_n_fobj.fieldn = 'Normalized Var * N'
            
            wpobj = copy.deepcopy(fobj)
            if wpobj.dims == 3:
                wpobj.data = fobj.data[0]
                wpobj.dims = 2
            
            
            # Plotting
            if 'var' in plotlist or 'all' in plotlist:
                fobjlist_plot = [wpobj, MP_fobj, nvar_n_fobj, mp_fobj]
                cmlist = [(cmWP, levelsWP), (cmMP, levelsMP*np.nanmax(MP_fullfield)), 
                        (cmNVAR, levelsNVAR), (cmMP, levelsMP*np.nanmax(mp_fullfield))]
                
                fig, axarr = plt.subplots(2, 2, figsize = (9, 8))
                for ax, fob, cm, i in zip(list(np.ravel(axarr)), fobjlist_plot, cmlist, 
                                                        range(4)):
                    plt.sca(ax)   # This is necessary for some reason...
                    cf, tmp = ax_contourf(ax, fob, colors=cm[0], 
                                        pllevels=cm[1], sp_title=fob.fieldn,
                                        Basemap_drawrivers = False,
                                        npars = 0, nmers = 0, ji0=(lx1, ly1),
                                        ji1=(sxo+lx2, syo+ly2), extend = 'both')
                    cb = fig.colorbar(cf)
                    cb.set_label(fob.unit)
                plotttitle = (date + '+' + ddhhmmss(t) + ' ' + ana + ' water=' + 
                            str(water) + ' n = ' + str(n).zfill(3) + ' ' + realhstr)
                fig.suptitle(plotttitle, fontsize='x-large')
                plt.tight_layout(rect=[0, 0.03, 1, 0.95])  # To account for suptitle
                plotdirnew = plotdir + '/var/'
                if not os.path.exists(plotdirnew): os.makedirs(plotdirnew)
                fig.savefig(plotdirnew + 'var_' + ddhhmmss(t) + '_' + 
                            str(n).zfill(3) + '_lev' + str(lev),
                            dpi = 300)
                plt.close('all')
            
            # Now actually calculate the variance constant/factor
            # Method 1: Simply take the mean of nvar 
            varres1list.append([var/(MPmean**2), Nmean])
            
            # Method 2: Do the slope approach
            
            #xfit = np.ravel(MPmean**2)
            #yfit = np.ravel(var)
            #mask = yfit > 0
            
            nvar_n_list[i_n].append(np.nanmean(nvar_n_fobj.data)/2.)  # NOTE Divide by 2
            var_n_over_n[i_n].append(np.nanmean(Nvar/Nmean))
            adj_nvar_n_list[i_n].append(np.nanmean(nvar_n_fobj.data)/
                                        (1 + np.nanmean(Nvar/Nmean)))
            
            #slope = leastsq(origin_residual, 1, args = (xfit[mask], yfit[mask]))[0][0]
            #varres2list.append([np.sqrt(slope), np.sqrt(1/np.nanmean(Nmean))])
        # End n loop
        varres1list = np.array(varres1list)
        #varres2list = np.array(varres2list)
        

        
        # Plot what needs to be plotted every time step
        # 1. Ensemble mean tau_c over Germany
        if 'tauc' in plotlist or 'all' in plotlist:
            title_sufx = 'mean tau_c, di_mean: ' + str(dimeantauc) + 'h + ' + ddhhmmss(t)
            fig = fig_contourf_1sp(meantauc, pllevels = np.arange(0, 21, 1),
                                extend = 'max', sp_title = title_sufx,
                                Basemap_drawrivers = False,
                                ji0=(lx1, ly1), ji1=(sxo+lx2, syo+ly2))
            plt.tight_layout()
            plotdirnew = plotdir + '/tauc/'
            if not os.path.exists(plotdirnew): os.makedirs(plotdirnew)
            fig.savefig(plotdirnew + 'tauc_' + ddhhmmss(t), dpi = 300)
        
        if 'stats' in plotlist or 'all' in plotlist:
            # 2. Plot cloud size and m/p distribution, plus RDF
            fig, axarr = plt.subplots(1, 3, figsize = (95./25.4*2.5, 3.2))
            axarr[0].bar(sizeedges[:-1], sizehist, width = np.diff(sizeedges)[0])
            axarr[0].plot([sizemean, sizemean], [0.1, 1e4], c = 'red', 
                        alpha = 0.5)
            axarr[0].set_xlabel('Cloud size [m^2]')
            axarr[0].set_ylabel('Number of clouds')
            axarr[0].set_title('Cloud size distribution')
            axarr[0].set_xlim([0., sizemax])
            axarr[0].set_ylim([0.1, 1e4])
            axarr[0].set_yscale('log')
            
            axarr[1].bar(sumedges[:-1], sumhist, width = np.diff(sumedges)[0])
            axarr[1].plot([summean, summean], [0.1, 1e4], c = 'red', 
                        alpha = 0.5)
            axarr[1].set_ylabel('Number of clouds')
            axarr[1].set_xlim([0., summax])
            axarr[1].set_ylim([0.1, 1e4])
            axarr[1].set_yscale('log')
            
            # 3. Plot RDF
            axarr[2].plot(r/1000., g)
            axarr[2].plot([r_cluster, r_cluster], [0, 4], c = 'red', alpha = 0.5)
            axarr[2].plot([0, np.max(r)/1000.], [1, 1], c = 'gray', alpha = 0.5)
            
            # Plot CDF 
            axarr[2].plot(r/1000., g_cdf, c = 'g')
            axarr[2].plot([r_cdf_cluster, r_cdf_cluster], [0, 4], c = 'pink', alpha = 0.5)
        
            axarr[2].set_xlabel('Distance [km]')
            axarr[2].set_ylabel('Normalized RDF')
            axarr[2].set_title('Radial distribution function')
            axarr[2].set_ylim(0, 4)
            axarr[2].set_xlim(0, np.max(r)/1000.)
                
            # Analysis specific stuff
            if ana == 'm':
                axarr[1].set_xlabel('Cloud mass flux [kg/s]')
                axarr[1].set_title('Cloud mass flux distribution')
            
            else: 
                axarr[1].set_xlabel('Cloud precipitation [mm/h]')
                axarr[1].set_title('Cloud precipitation distribution')
                
            plotttitle = (date + '+' + ddhhmmss(t) + ' ' + ana + ' water=' + 
                        str(water) + ' ' + realhstr)
            fig.suptitle(plotttitle, fontsize='x-large')
            plt.tight_layout(rect=[0, 0.0, 1, 0.95])
            plotdirnew = plotdir + '/cloud_stats/'
            if not os.path.exists(plotdirnew): os.makedirs(plotdirnew)
            fig.savefig(plotdirnew + 'stats_' + ddhhmmss(t) + '_lev' + str(lev),
                        dpi = 300)
        
        if 'scatter' in plotlist or 'all' in plotlist:
            # 4. Plot CC06 Fig4 
            fig, axarr = plt.subplots(1, 2, figsize = (95./25.4*2, 3.2))
        
            for x, y, n, c in zip(list(varres1list[:,1]),
                                list(varres1list[:,0]),
                                nlist, clist):
                x[x==0] = np.nan   # Set no clouds to nan for correct mean
        
                xcloud = np.sqrt(1/x)
                ycloud = np.sqrt(y)
                
                # Get mean 
                xmean = 10**(np.mean(np.log10(xcloud[np.isfinite(xcloud*ycloud)])))
                ymean = 10**(np.mean(np.log10(ycloud[np.isfinite(xcloud*ycloud)])))
                #xmean = np.nanmean(xcloud)
                #ymean = np.nanmean(ycloud)
                
                #ax.scatter(x, y, marker = 'D', c = c, label = str(n*2.8)+'km', s = 20,
                        #linewidth = 0.2)
                axarr[0].scatter(xcloud, ycloud, marker = 'o', c = c, 
                        s = 4, zorder = 0.2, linewidth = 0, alpha = 0.8,
                        label = str(n*2.8)+'km')
                
                
                axarr[0].scatter(xmean, ymean, marker = 'x', c = c, 
                        s = 18, zorder = 0.5, linewidth = 2, alpha = 1)
        
                ypercent = y/(2./x)*100.
                ypercent_mean = np.mean(ypercent[np.isfinite(xcloud*ycloud)])
                axarr[1].scatter(xcloud, ypercent, marker = 'o', c = c, 
                        s = 4, zorder = 0.2, linewidth = 0, alpha = 0.8)
                axarr[1].scatter(xmean, ypercent_mean, marker = 'x', c = c, 
                        s = 18, zorder = 0.5, linewidth = 2, alpha = 1)
            
            #for x, y, n, c in zip(list(varres2list[:,1]),
                                #list(varres2list[:,0]),
                                #nlist, clist): 
                #ax.scatter(x, y, marker = '*', c = c, label = str(n*2.8)+'km', s = 20,
                        #linewidth = 0.2)
            
            axarr[0].legend(loc =3, ncol = 2, prop={'size':6})
            tmp = np.array([0,10])
            axarr[0].plot(tmp,tmp*np.sqrt(2), c = 'gray', alpha = 0.5, linestyle = '--',
                    zorder = 0.1)
            axarr[0].set_xlim(0.05,10)
            axarr[0].set_ylim(0.01,100)
            axarr[0].set_xscale('log')
            axarr[0].set_yscale('log')
            axarr[0].invert_xaxis()
            axarr[0].set_xlabel('Square root (1/N)')
            if ana == 'm':
                axarr[0].set_ylabel('Square root (Var(M)/M^2)')
            else:
                axarr[0].set_ylabel('Square root (Var(P)/P^2)')
            axarr[1].plot([0.,10],[100,100], c = 'gray', alpha = 0.5, linestyle = '--',
                    zorder = 0.1)
            axarr[1].set_xlim(0.05,10)
            axarr[1].set_ylim(1, 1000)
            axarr[1].set_xscale('log')
            axarr[1].set_yscale('log')
            axarr[1].invert_xaxis()
            axarr[1].set_xlabel('Square root (1/N)')
            axarr[1].set_ylabel('Percent of theoretical value')
            plotttitle = (date + '+' + ddhhmmss(t) + ' ' + ana + ' water=' + 
                        str(water) + ' ' + realhstr)
            fig.suptitle(plotttitle, fontsize='x-large')
            plt.tight_layout(rect=[0, 0.0, 1, 0.95])
            plotdirnew = plotdir + '/var_scatter/'
            if not os.path.exists(plotdirnew): os.makedirs(plotdirnew)
            fig.savefig(plotdirnew + 'scatter_' + ddhhmmss(t) + '_lev' + str(lev), 
                        dpi = 300)
            plt.close('all')
        
    # End time loop
        
        
    # Plot summary plots
    if 'summary' in plotlist or 'all' in plotlist:
        timelist_plot = [(dt.total_seconds()/3600) for dt in timelist]
        
        # First plot
        fig, axarr = plt.subplots(2, 2, figsize = (95./25.4*3, 7.))
        
        axarr[0,0].plot(timelist_plot, total_list)
        axarr[0,0].set_xlabel('time [h/UTC]')
        axarr[0,0].set_xlim(timelist_plot[0], timelist_plot[-1])
        
        axarr[0,1].plot(timelist_plot, sizemmean_list)
        axarr[0,1].set_xlabel('time [h/UTC]')
        axarr[0,1].set_ylabel('Mean cloud size [m^2]')
        axarr[0,1].set_xlim(timelist_plot[0], timelist_plot[-1])
        
        axarr[1,0].plot(timelist_plot, dimeantauc_list)
        axarr[1,0].set_xlabel('time [h/UTC]')
        axarr[1,0].set_ylabel('Domain mean tau_c [h]')
        axarr[1,0].set_xlim(timelist_plot[0], timelist_plot[-1])
        
        axarr[1,1].plot(timelist_plot, summean_list)
        axarr[1,1].set_xlabel('time [h/UTC]')
        axarr[1,1].set_xlim(timelist_plot[0], timelist_plot[-1])
        
        if ana == 'm':
            axarr[0,0].set_ylabel('Domain total mass flux [kg/s]')
            axarr[1,1].set_ylabel('Mean cloud mass flux [kg/s]')
            
        else:
            axarr[0,0].set_ylabel('Domain total precipitation rate [mm/h]')
            axarr[1,1].set_ylabel('Mean cloud precipitation rate [mm/h]')
        plotttitle = (date + ' ' + ana + ' water=' + 
                        str(water) + ' ' + realhstr)
        fig.suptitle(plotttitle, fontsize='x-large')
        plt.tight_layout(rect=[0, 0.0, 1, 0.95])
        fig.savefig(plotdir + 'mean_stats_timeseries' + '_lev' + str(lev))
        
        
        
        # Second plot
        # Loop over nlist
        fig, axarr = plt.subplots(2, 2, figsize = (95./25.4*3, 7.))
        
        for i, n in enumerate(nlist):
            axarr[0,0].plot(timelist_plot, var_n_over_n[i], c = clist[i], 
                            label = str(n*2.8)+'km')
            axarr[0,0].plot(timelist_plot, [1.]*len(timelist_plot), c = 'gray', 
                            zorder = 0.1)
            axarr[0,0].set_xlabel('time [h/UTC]')
            axarr[0,0].set_ylabel('Var(N)/N')
            axarr[0,0].set_xlim(timelist_plot[0], timelist_plot[-1])
            
            axarr[0,1].plot(timelist_plot, nvar_n_list[i], c = clist[i], 
                            label = str(n*2.8)+'km')
            axarr[0,1].plot(timelist_plot, [1.]*len(timelist_plot), c = 'gray', 
                            zorder = 0.1)
            axarr[0,1].set_xlabel('time [h/UTC]')
            axarr[0,1].set_ylabel('0.5 * NVar(M) <N>')
            axarr[0,1].set_xlim(timelist_plot[0], timelist_plot[-1])
            
            axarr[1,1].plot(timelist_plot, adj_nvar_n_list[i], c = clist[i], 
                            label = str(n*2.8)+'km')
            axarr[1,1].plot(timelist_plot, [1]*len(timelist_plot), c = 'gray', 
                            zorder = 0.1)
            axarr[1,1].set_xlabel('time [h/UTC]')
            axarr[1,1].set_ylabel('NVar(M) <N> / (1+Var(N)/N)')
            axarr[1,1].set_xlim(timelist_plot[0], timelist_plot[-1])
            axarr[1,1].legend(loc =3, ncol = 2, prop={'size':6})
        
            plotttitle = (date + ' ' + ana + ' water=' + 
                        str(water) + ' ' + realhstr)
            
        fig.suptitle(plotttitle, fontsize='x-large')
        plt.tight_layout(rect=[0, 0.0, 1, 0.95])
        fig.savefig(plotdir + 'variance_stats_timeseries' + '_lev' + str(lev))
            
        
    ## Plot correlation plots
    #if 'corr' in plotlist:
        ## convert to numpy arrays
        #var_alllist = np.array(var_alllist)
        #M_alllist = np.array(M_alllist)
        #m_alllist = np.array(m_alllist)
        #N_alllist = np.array(N_alllist)
        #n_alllist = np.array(n_alllist)
        #tauc_alllist = np.array(tauc_alllist)
        #UTC_alllist = np.array(UTC_alllist)
        
        ## save lists
        #list_names = ['var', 'M', 'm', 'N', 'n', 'tauc', 'UTC']
        #list_list = [var_alllist, M_alllist, m_alllist, N_alllist, n_alllist,
                    #tauc_alllist, UTC_alllist]
        #np.save('./results/corr_' + date + '.npy', (list_names, list_list))
        
        #x = var_alllist/(M_alllist*M_alllist/N_alllist)
        #y = tauc_alllist
        
        #fig, ax = plt.subplots(1, 1, figsize = (95./25.4, 3.2))
        #ax.scatter(x, y)
        #fig.savefig(plotdir + 'corr_test', dpi = 300)
        #nanmask = np.isfinite(x) * np.isfinite(y)
        #print np.corrcoef(x[nanmask], y[nanmask])[1,0]




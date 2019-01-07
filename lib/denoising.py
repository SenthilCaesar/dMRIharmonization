#!/usr/bin/env python
import warnings
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=FutureWarning)

    from dipy.io.image import load_nifti
    from dipy.io import read_bvals_bvecs

from scipy.io import savemat
import numpy as np



def denoising(dwi, mask=None):

    '''
    #  [Signal, Sigma] = MPdenoising(data, mask, kernel, sampling)
    #       output:
    #           - Signal: [x, y, z, M] denoised data matrix
    #           - Sigma: [x, y, z] noise map
    #       input:
    #           - data: [x, y, z, M] data matrix
    #           - mask:   (optional)  region-of-interest [boolean]
    #           - kernel: (optional)  window size, typically in order of [5 x 5 x 5]
    #           - sampling:
    #                    full: sliding window (default for noise map estimation, i.e. [Signal, Sigma] = MPdenoising(...) )
    #
    # REFERENCES
    #      Veraart, J.; Fieremans, E. & Novikov, D.S. Diffusion MRI noise mapping
    #      using random matrix theory Magn. Res. Med., 2016, early view, doi:
    #      10.1002/mrm.26059

    '''


    sx, sy, sz, M = dwi.shape

    if mask is None:
        mask = np.ones((sx, sy, sz), dtype= 'int')

    kernel = np.array([5, 5, 5])
    k = [int((x-1)/2) for x in kernel]
    kx = k[0]
    ky = k[1]
    kz = k[2]
    N = kernel.prod()

    mask[ : k[0] ,: ,: ] = 0
    mask[ -k[0]: ,: ,: ] = 0

    mask[ :, : k[1] ,: ] = 0
    mask[ :, -k[1]: ,: ] = 0

    mask[ :, :, : k[2] ] = 0
    mask[ :, :, -k[2]: ] = 0


    def flat_list(l):
        return [item for sublist in l for item in sublist]

    x = []
    y = []
    z = []
    for i in range(k[2],sz-k[2]):
        x_, y_ = np.where(mask[:,:,i] == 1.)
        if len(x_):
            x.append(x_)
            y.append(y_)
            z.append([i]*len(y_))

    x = flat_list(x)
    y = flat_list(y)
    z = flat_list(z)

    sigma  = np.zeros(len(x), dtype= 'float')
    # npars  = np.zeros(len(x), dtype= 'float')
    signal = np.zeros((M, N, len(x)), dtype= 'float')

    Sigma  = np.zeros((sx, sy, sz), dtype= 'float')
    # Npars  = np.zeros((sx, sy, sz), dtype= 'float')
    Signal = np.zeros((sx, sy, sz, M), dtype= 'float')


    # compute scaling factor for N<M
    R = min(M, N)
    maxMN= max(M, N)
    scaling = np.array([(maxMN - float(x))/N for x in range(R)])


    # start denoising
    for nn in range(len(x)):
        # create data matrix
        X = dwi[x[nn]-kx:x[nn]+kx+1, y[nn]-ky:y[nn]+ky+1, z[nn]-kz:z[nn]+kz+1,: ]
        X = np.reshape(X, (N, M)).T

        # compute PCA eigenvalues
        u, vals, v = np.linalg.svd(X, full_matrices= False)
        vals = vals**2 / N

        # debug block
        if x[nn]== 46 and y[nn]== 42 and z[nn]== 7:
            print('Wait')

        # First estimation of Sigma^2;  Eq 1 from ISMRM presentation
        csum = np.cumsum(vals[::-1])
        cmean = csum/np.array([i for i in range(1,R+1)])
        sigmasq_1 = cmean[::-1]/scaling

        # Second estimation of Sigma^2; Eq 2 from ISMRM presentation
        gamma = [(M - float(i))/N for i in range(R)]
        rangeMP = 4*np.sqrt(gamma)
        rangeData = vals - vals[R-1]
        sigmasq_2 = rangeData/rangeMP

        # sigmasq_2 > sigma_sq1 if signal components are represented in the eigenvalues
        t = np.where(sigmasq_2 < sigmasq_1)[0][0]

        if t==[]:
            sigma[nn] = np.nan
            signal[:, :, nn] = X
            t = R
        else:
            sigma[nn] = np.sqrt(sigmasq_1[t])
            vals[t:R] = 0
            s = u @ np.diag(np.sqrt(N*vals)) @ v
            signal[:, :, nn] = s

        # npars[nn] = t


    ceilInd= int(np.ceil(kernel.prod()/2))
    for nn in range(len(x)):
        Sigma[x[nn], y[nn], z[nn]] = sigma[nn]
        # Npars[x[nn], y[nn], z[nn]] = npars[nn]
        Signal[x[nn], y[nn],z[nn], :] = signal[ :,ceilInd,nn]

    return (Signal, Sigma)


if __name__=='__main__':

    dwi=load_nifti('/home/tb571/Downloads/Harmonization-Python/connectom_prisma_demoData/A/connectom/dwi_A_connectom_st_b1200.nii.gz')[0]
    mask= load_nifti('/home/tb571/Downloads/Harmonization-Python/connectom_prisma_demoData/A/connectom/mask.nii.gz')[0]
    Signal, Sigma= denoising(dwi, mask)


    bvals, _= read_bvals_bvecs(
        '/home/tb571/Downloads/Harmonization-Python/connectom_prisma_demoData/A/connectom/dwi_A_connectom_st_b1200.bval',
        '/home/tb571/Downloads/Harmonization-Python/connectom_prisma_demoData/A/connectom/dwi_A_connectom_st_b1200.bvec')
    savemat('/home/tb571/Downloads/Harmonization-Python/connectom_prisma_demoData/denoise/img_data.mat',
            {'pySignal':Signal, 'pySigma':Sigma, 'dwi': dwi, 'mask':mask})

    # savemat('/home/tb571/Downloads/Harmonization-Python/connectom_prisma_demoData/denoise/xyz_data.mat',{'x':x, 'y':y, 'z':z})
    # np.take(Signal, np.where(bvals != 0.)[0], axis=3)
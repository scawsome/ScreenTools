import numpy as np
import numpy.ma as ma
import logging
import h5py
import matplotlib.pyplot as plt
from scipy import ndimage

from .processing import thresholding
from .processing import masking
from .processing import cropping
from . import utils



class ImageBox:
    ''' 
    class to store and transform scaling for images for pixel->real space
    '''
    def __init__(self):
        self.center = np.asfarray([0,0])
        self.size = np.asfarray([1,1])

    def set_center(self,center):
        self.center = center

    def set_size(self,size):
        self.size = size

    def set_bbox(self,coords):
        ''' coords in the form [[x0,y0],[x1,y1]]
        where 
        (x0,y0) is bottom left and
        (x1,y1) is bottom right
        '''
        if not type(coords) == np.ndarray:
            coords = np.asfarray(coords)
        self.center = np.asfarray(((coords[0][0] + coords[1][0])/2,(coords[0][1] + coords[1][1])/2))
        self.size = np.asfarray((coords[1][0]-coords[0][0],coords[1][1] - coords[0][1]))

    def check_type(self):
        if not type(self.center) == np.ndarray:
            self.center = np.asfarray(self.center)
        if not type(self.size) == np.ndarray:
            self.size = np.asfarray(self.size)
    
    def get_bbox(self):
        self.check_type()
        v0 = self.center - self.size / 2
        v1 = self.center + self.size / 2
        return np.vstack(v0,v1)

    def get_extent(self):
        self.check_type()
        v0 = self.center - self.size / 2
        v1 = self.center + self.size / 2
        return [v0[0],v1[0],v0[1],v1[1]]

def quick_process_file(files):
    for f in files:
        mask_file(f)
        filter_file(f)
    for f in files:
        threshold_file(f,manual=True)

def quick_process_frame(f,frame_number):
    mask_frame(f,frame_number)
    #filter_frame(f,frame_number)
    threshold_frame(f,frame_number=frame_number,manual=True)
    
def mask_file(h5file):
    '''
    masks all images in <h5file>
    '''
    return masking.mask_file(h5file)

def mask_frame(h5file,frame_number):
    return masking.mask_frame(h5file,frame_number)

def threshold_frame(h5file,manual=False,frame_number=-1,level=0):
    if manual:
        m = thresholding.ManualThresholdSelector(h5file,frame_number)
    else:
        thresholding.set_threshold(h5file,level,frame_number)

    thresholding.apply_threshold(h5file,frame_number)

def threshold_file(h5file,level=0,manual=False,overwrite=False,plotting=False):
    logging.info('thresholding {}'.format(h5file))
    with h5py.File(h5file) as f:
        try:
            a = f['/0'].attrs['threshold']
            if a:
                is_thresholded = True
            else:
                is_thresholded = False
        except KeyError:
            is_thresholded = False

    if plotting:
        thresholding.plot_threshold(h5file)
        return h5file
            
    if not is_thresholded or overwrite:
        frames = utils.get_frames(h5file)
        if manual:
            thresholding.ManualThresholdSelector(h5file,0)
            m = utils.get_attr(h5file,'threshold','/0')
            thresholding.set_threshold(h5file,m)
        else:
            thresholding.set_threshold(h5file,level)
            
        thresholding.apply_threshold(h5file)
    return h5file

def get_rect_crop(h5file,frame_number):
    c = cropping.ManualRectangleCrop(h5file,frame_number)
    return c.get_rectangle_extent()


def crop_frame(h5file,extent = '',frame_number=0):
    #add ability to recall cropping OR get cropped rectangle and use rectangle in the future to keep settings -Ryan
    if extent == '':
        extent = get_rect_crop(h5file,frame_number)
    
    cropping.rectangle_crop(h5file,extent,frame_number)

def crop_file(h5file,extent=''):
    if extent == '':
        extent = get_rect_crop(h5file,0)
        
    cropping.rectangle_crop(h5file,extent,-1)

        
        
def filter_array(array,sigma=1,size=4):
    ''' apply a median filter and a gaussian filter to image'''
    ndata = ndimage.median_filter(array,size)
    return ndata
    #return ndimage.gaussian_filter(ndata,sigma)

def filter_frame(h5file,frame_number):
    with h5py.File(h5file,'r+') as f:
        dataset = f['/{}/img'.format(frame_number)]
        try:
            filtered_already = dataset.attrs['filtered']
        except KeyError:
            filtered_already = False
            
        if not filtered_already:
            narray = filter_array(dataset[:])
            dataset[...] = narray
            dataset.attrs['filtered'] = 1
    
def filter_file(h5file):
    '''filtering'''
    if not utils.get_attr(h5file,'filtered',dataset='/img/0'):
        logging.info('applying median filter to file {}'.format(h5file))

        for i in utils.get_frames(h5file):
            logging.debug('filtering frame {}'.format(i))
            filter_frame(h5file,i)
                
def reset_frame(h5file,frame_number=0):
    logging.debug('resetting image {}'.format(frame_number,h5file))
    with h5py.File(h5file,'r+') as f:
        del f['/{}/img'.format(frame_number)]
        raw = f['/{}/raw'.format(frame_number)][:]

        f.create_dataset('/{}/img'.format(frame_number),data=raw)
        f['/{}/'.format(frame_number)].attrs['threshold'] = 0
        f['/{}/'.format(frame_number)].attrs['filtered'] = 0
        
        
def reset_file(h5file):
    logging.info('resetting file {}'.format(h5file))
    for i in range(utils.get_attr(h5file,'nframes')-1):
        reset_frame(h5file,i)
    with h5py.File(h5file,'r+') as f:
        names = ['filtered','background_removed','masked','global_threshold']
        for name in names:
            try:
                del f.attrs[name]
            except KeyError:
                pass

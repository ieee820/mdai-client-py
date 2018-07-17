import pandas as pd 
import pydicom
import numpy as np
import colorsys
import random

import cv2 

from skimage.measure import find_contours
import matplotlib.pyplot as plt
from matplotlib import patches,  lines
from matplotlib.patches import Polygon
import IPython.display

""" Visualization utility functions. 
"""

# TODO: move mdai-api-test.ipynb to mdai-client-py/notebooks directory 
# TODO: color should be exported in json labels 

# TODO: put CONFIG VALUES in config.py 
ORIG_HEIGHT = 1024
ORIG_WIDTH  = 1024 

# example: 
# class Config(object): 
#     NAME = None 

# class DisplayConfig(Config): 
#     pass 

# Adapted from https://github.com/matterport/Mask_RCNN/

def random_colors(N, bright=True):
    """
    Generate random colors.
    To get visually distinct colors, generate them in HSV space then
    convert to RGB.
    """
    brightness = 1.0 if bright else 0.7
    hsv = [(i / N, 1, brightness) for i in range(N)]
    colors = list(map(lambda c: colorsys.hsv_to_rgb(*c), hsv))
    random.shuffle(colors)
    return colors

# TODO: figsize should be read from settings 
def display_images(image_ids, titles=None, cols=3, 
                   cmap=None, norm=None, interpolation=None):    
    titles = titles if titles is not None else [""] * len(image_ids)
    rows = len(image_ids) // cols + 1
    plt.figure(figsize=(14, 14 * rows // cols))
    i = 1
    for image_id, title in zip(image_ids, titles):
        plt.subplot(rows, cols, i)
        plt.title(title, fontsize=9)
        plt.axis('off')

        ds = pydicom.read_file(image_id)
        image = ds.pixel_array
        # If grayscale. Convert to RGB for consistency.
        if len(image.shape) != 3 or image.shape[2] != 3:
            image = np.stack((image,) * 3, -1)
        plt.imshow(image.astype(np.uint8), cmap=cmap,
                   norm=norm, interpolation=interpolation)
        
        i += 1
    plt.show()

def load_dicom_image(image_id, to_RGB=False):
    """ Load a DICOM image."""
    ds = pydicom.read_file(image_id)
    image = ds.pixel_array
    
    #TODO: decide if to_RGB should be true/false by default
    if to_RGB: 
        # If grayscale. Convert to RGB for consistency.
        if len(image.shape) != 3 or image.shape[2] != 3:
            image = np.stack((image,) * 3, -1)

    return image 

# TODO: Need to handle loading for Free Form, Line, Polygon, Bounding Box and Thresholded Box.
def load_mask(dataset, image_id, label_ids_dict):
    """ Load instance masks for the given image. 
        Masks can be different types, mask is a binary true/false map of the same 
        size as the image.
    """
    annotations = dataset[image_id]
    count = len(annotations)
    print('Number of annotations: %d' % count)
    
    # TODO: mask should use image size (use ORIG_HEIGHT/WIDTH set in config file?)
    if count == 0:
        print('No annotations')
        mask = np.zeros((ORIG_HEIGHT, ORIG_WIDTH, 1), dtype=np.uint8)
        class_ids = np.zeros((1,), dtype=np.int32)
    else:
        mask = np.zeros((ORIG_HEIGHT, ORIG_WIDTH, count), dtype=np.uint8)
        class_ids = np.zeros((count,), dtype=np.int32)

        for i, a in enumerate(annotations):

            # TODO: select by annotation mode (bbox, polygon, freeform, etc) 

            # Bounding Box  
            x = int(a['data']['x'])
            y = int(a['data']['y'])
            w = int(a['data']['width'])
            h = int(a['data']['height'])
            mask_instance = mask[:, :, i].copy()
            cv2.rectangle(mask_instance, (x, y), (x+w, y+h), 255, -1)
            mask[:, :, i] = mask_instance

            # FreeForm 

            # Line 

            # Polygon 

            # Thresholded Box (defer for now)

            # load class id 
            if a['labelId'] in label_ids_dict:
                class_ids[i] = label_ids_dict[a['labelId']]['class_id']

    return mask.astype(np.bool), class_ids.astype(np.int32)

def apply_mask(image, mask, color, alpha=0.5):
    """Apply the given mask to the image.
    image: [height, widht, channel] 
    Returns: image with applied color mask 
    """
    for c in range(3):
        image[:, :, c] = np.where(mask == 1,
                                  image[:, :, c] *
                                  (1 - alpha) + alpha * color[c] * 255,
                                  image[:, :, c])
    return image

def extract_bboxes(mask):
    """Compute bounding boxes from masks.
    mask: [height, width, num_instances]. Mask pixels are either 1 or 0.
    Returns: bbox array [num_instances, (y1, x1, y2, x2)].
    """
    boxes = np.zeros([mask.shape[-1], 4], dtype=np.int32)
    for i in range(mask.shape[-1]):
        m = mask[:, :, i]
        # Bounding box.
        horizontal_indicies = np.where(np.any(m, axis=0))[0]
        vertical_indicies = np.where(np.any(m, axis=1))[0]
        if horizontal_indicies.shape[0]:
            x1, x2 = horizontal_indicies[[0, -1]]
            y1, y2 = vertical_indicies[[0, -1]]
            # x2 and y2 should not be part of the box. Increment by 1.
            x2 += 1
            y2 += 1
        else:
            # No mask for this instance. Might happen due to
            # resizing or cropping. Set bbox to zeros
            x1, x2, y1, y2 = 0, 0, 0, 0
        boxes[i] = np.array([y1, x1, y2, x2])
    return boxes.astype(np.int32)

# TODO: not all have bounding boxes, should this be an option? 
def get_image_ground_truth(dataset, image_id, label_ids):
    """Load and return ground truth data for an image (image, mask, bounding boxes).
    Input: 
        dataset: 
        image_id:         
    Returns:
        image: [height, width, 3]
        shape: the original shape of the image before resizing and cropping.
        class_ids: [instance_count] Integer class IDs
        bbox: [instance_count, (y1, x1, y2, x2)]
        mask: [height, width, instance_count]. The height and width are those
            of the image unless use_mini_mask is True, in which case they are
            defined in MINI_MASK_SHAPE.
    """ 

    # TODO: auto-detect image type? 
    image = load_dicom_image(image_id, to_RGB=True)

    mask, class_ids = load_mask(dataset, image_id, label_ids)
    
    original_shape = image.shape
    
    # TODO: need to resize image, mask?    
    _idx = np.sum(mask, axis=(0, 1)) > 0
    mask = mask[:, :, _idx]
    class_ids = class_ids[_idx]
    
    # Bounding boxes. Note that some boxes might be all zeros
    # if the corresponding mask got cropped out.
    # bbox: [num_instances, (y1, x1, y2, x2)]
    bbox = extract_bboxes(mask)
    
    return image, class_ids, bbox, mask


def display_annotations(image, boxes, masks, class_ids, class_names,
                      scores=None, title="",
                      figsize=(16, 16), ax=None,
                      show_mask=True, show_bbox=True,
                      colors=None, captions=None):
    """
    boxes: [num_instance, (y1, x1, y2, x2, class_id)] in image coordinates.
    masks: [height, width, num_instances]
    class_ids: [num_instances]
    class_names: list of class names of the dataset
    scores: (optional) confidence scores for each box
    title: (optional) Figure title
    show_mask, show_bbox: To show masks and bounding boxes or not
    figsize: (optional) the size of the image
    colors: (optional) An array or colors to use with each object
    captions: (optional) A list of strings to use as captions for each object
    """
    # Number of instancesload_mask
    N = boxes.shape[0]
    if not N:
        print("\n*** No instances to display *** \n")
    else:
        assert boxes.shape[0] == masks.shape[-1] == class_ids.shape[0]

    # If no axis is passed, create one and automatically call show()
    auto_show = False
    if not ax:
        _, ax = plt.subplots(1, figsize=figsize)
        auto_show = True

    # Generate random colors
    colors = colors or random_colors(N)

    # Show area outside image boundaries.
    height, width = image.shape[:2]
    ax.set_ylim(height + 10, -10)
    ax.set_xlim(-10, width + 10)
    ax.axis('off')
    ax.set_title(title)

    masked_image = image.astype(np.uint32).copy()
    for i in range(N):
        color = colors[i]

        # Bounding box
        if not np.any(boxes[i]):
            # Skip this instance. Has no bbox. Likely lost in image cropping.
            continue
        y1, x1, y2, x2 = boxes[i]
        if show_bbox:
            p = patches.Rectangle((x1, y1), x2 - x1, y2 - y1, linewidth=2,
                                alpha=0.7, linestyle="dashed",
                                edgecolor=color, facecolor='none')
            ax.add_patch(p)

        # Label
        if not captions:
            class_id = class_ids[i]
            score = scores[i] if scores is not None else None

            # BUG: THIS IS A HACK! THIS IS BECAUSE class_id does not start from zero! 
            label = class_names[class_id-1]
            x = random.randint(x1, (x1 + x2) // 2)
            caption = "{} {:.3f}".format(label, score) if score else label
        else:
            caption = captions[i]
        ax.text(x1, y1 + 8, caption,
                color='w', size=11, backgroundcolor="none")

        # Mask
        mask = masks[:, :, i]
        if show_mask:
            masked_image = apply_mask(masked_image, mask, color)

        # Mask Polygon
        # Pad to ensure proper polygons for masks that touch image edges.
        padded_mask = np.zeros(
            (mask.shape[0] + 2, mask.shape[1] + 2), dtype=np.uint8)
        padded_mask[1:-1, 1:-1] = mask
        contours = find_contours(padded_mask, 0.5)
        for verts in contours:
            # Subtract the padding and flip (y, x) to (x, y)
            verts = np.fliplr(verts) - 1
            p = Polygon(verts, facecolor="none", edgecolor=color)
            ax.add_patch(p)
    ax.imshow(masked_image.astype(np.uint8))
    if auto_show:
        plt.show()

def draw_box_on_image(image, boxes, h, w):
    """Draw box on an image. 
    Params: 
        image: three channel (e.g. RGB) image 
        boxes: normalized box coordinate (between 0.0 and 1.0)
        h: image height 
        w: image width 
    """ 

    for i in range(len(boxes)):
        (left, right, top, bottom) = (boxes[i][0] * w, boxes[i][2] * w,
                                      boxes[i][1] * h, boxes[i][3] * h)
        p1 = (int(left), int(top))
        p2 = (int(right), int(bottom))
        cv2.rectangle(image, p1, p2, (77, 255, 9), 3, 1)
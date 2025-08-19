import torch
import numpy as np


def srgb2linear_rgb(image):
    """
    convert linear rgb image to srgb image
    Args:
        image (numpy array): linear rgb color space image

    Returns:
        image (numpy array): srgb color space image
    """
    return np.where(image <= 0.04045, image / 12.92, ((image + 0.055) / 1.055) ** 2.4)


def linear_rgb2srgb(image):
    """
    convert srgb image to linear rgb image
    Args:
        image (numpy array): srgb color space image

    Returns:
        image (numpy array): linear rgb color space image
    """
    return np.where(image <= 0.003130804953560372, image * 12.92, 1.055 * (image ** (1.0 / 2.4)) - 0.055)


def preprocessing_image(image):
    """
    convert image(numpy array, unit8) to tensor
    Args:
        image (numpy array): character image (256x256, alpha channel included)
    Returns:
        tensor
    """
    np_image = np.array(image) / 255
    clipped_image = np.clip(np_image, 0, 1)
    srgb_image = srgb2linear_rgb(clipped_image)
    h, w, c = srgb_image.shape
    linear_image = srgb_image.reshape(h * w, c)
    for pixel in linear_image:
        if pixel[3] == 0.0:
            pixel[0:3] = 0.0
    reshaped_image = linear_image.transpose().reshape(c, h, w)
    return reshaped_image


def postprocessing_image(tensor):
    """
    convert tensor to image(numpy array, unit8)
    Args:
        tensor
    Returns:
        image (numpy array): character image (256x256, alpha channel included)
    """
    tensor = tensor.detach().squeeze(0)
    reshaped_tensor = tensor.permute(1, 2, 0)
    np_image = reshaped_tensor.numpy()
    np_image = (np_image + 1) / 2
    srgb_image = np_image[..., :3]
    alpha_image = np_image[..., 3]
    clipped_image = np.clip(srgb_image, 0, 1)
    rgb_image = srgb2linear_rgb(clipped_image)
    rgba_image = np.concatenate([rgb_image, alpha_image[..., np.newaxis]], axis=2)
    rgba_image = rgba_image * 255
    return rgba_image.astype(np.uint8)


def get_distance(a, b):
    """
    calculate euclidean distance a to b
    Args:
        a (landmark): 3d points
        b (landmark): 3d points

    Returns:
        L2 distance (float)
    """
    return np.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)

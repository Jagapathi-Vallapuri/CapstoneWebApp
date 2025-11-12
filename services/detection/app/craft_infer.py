

import torch
from torch.backends import cudnn
import torch.nn as nn
from torch.autograd import Variable
import cv2
import time
import numpy as np
from craft_pytorch import imgproc
from craft_pytorch import craft_utils

def test_net(net, image, text_threshold, link_threshold, low_text, cuda, poly, canvas_size=1280, mag_ratio=1.5, show_time=False, refine_net=None):
    t0 = time.time()

    # resize
    img_resized, target_ratio, size_heatmap = imgproc.resize_aspect_ratio(image, canvas_size, interpolation=cv2.INTER_LINEAR, mag_ratio=int(mag_ratio))
    ratio_h = ratio_w = 1 / target_ratio

    # preprocessing
    x = imgproc.normalizeMeanVariance(img_resized)
    x = torch.from_numpy(x).permute(2, 0, 1)    # [h, w, c] to [c, h, w]
    x = Variable(x.unsqueeze(0))                # [c, h, w] to [b, c, h, w]
    if cuda:
        x = x.cuda()

    # forward pass
    with torch.no_grad():
        y, feature = net(x)

    # make score and link map
    score_text = y[0,:,:,0].cpu().data.numpy()
    score_link = y[0,:,:,1].cpu().data.numpy()

    # refine link
    if refine_net is not None:
        with torch.no_grad():
            y_refiner = refine_net(y, feature)
        score_link = y_refiner[0,:,:,0].cpu().data.numpy()

    t0 = time.time() - t0
    t1 = time.time()

    # Post-processing
    boxes, polys = craft_utils.getDetBoxes(score_text, score_link, text_threshold, link_threshold, low_text, poly)

    # coordinate adjustment
    boxes = craft_utils.adjustResultCoordinates(boxes, ratio_w, ratio_h)
    polys = craft_utils.adjustResultCoordinates(polys, ratio_w, ratio_h)
    for k in range(len(polys)):
        if polys[k] is None: polys[k] = boxes[k]

    t1 = time.time() - t1

    # render results (optional)
    render_img = score_text.copy()
    render_img = np.hstack((render_img, score_link))
    ret_score_text = imgproc.cvt2HeatmapImg(render_img)

    if show_time:
        print("\ninfer/postproc time : {:.3f}/{:.3f}".format(t0, t1))

    return boxes, polys, ret_score_text

def detect_text(
    net,
    image,  # numpy array (e.g. from cv2.imread or file upload)
    text_threshold=0.7,
    link_threshold=0.4,
    low_text=0.4,
    cuda=True,
    poly=False,
    canvas_size=1280,
    mag_ratio=1.5,
    show_time=False,
    refine_net=None,
    return_type="boxes"  # "boxes" or "image"
):
    boxes, polys, _ = test_net(
        net, image, text_threshold, link_threshold, low_text, cuda, poly, canvas_size, mag_ratio, show_time, refine_net
    )

    if return_type == "boxes":
        return boxes
    elif return_type == "image":
        img_with_boxes = image.copy()
        for box in boxes:
            box = np.array(box).astype(np.int32).reshape((-1, 1, 2))
            cv2.polylines(img_with_boxes, [box], isClosed=True, color=(0, 255, 0), thickness=2)
        return img_with_boxes
    else:
        raise ValueError("return_type must be 'boxes' or 'image'")
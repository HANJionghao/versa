#!/usr/bin/env python3

# Copyright 2024 Jiatong Shi
#  Apache 2.0  (http://www.apache.org/licenses/LICENSE-2.0)


import os
import numpy as np
import librosa
import torch
import sys

import logging
from urllib.request import urlretrieve
import torch.nn as nn

sys.path.append("../../")

try:
    import fairseq
except ImportError:
    logging.warning(
        "fairseq is not installed. Please use `tools/install_fairseq.sh` to install"
    )

try:
    from tools.Noresqa.utils import (
        feats_loading,
        model_prediction_noresqa,
        model_prediction_noresqa_mos,
    )
    from tools.Noresqa.model import NORESQA

except ImportError:
    logging.warning(
        "noresqa is not installed. Please use `tools/install_noresqa.sh` to install"
    )
    Noresqa = None


def noresqa_model_setup(model_tag="default", metric_type=0, use_gpu=False):
    if use_gpu:
        device = "cuda"
    else:
        device = "cpu"

    if model_tag == "default":

        if not os.path.isdir("./checkpoints"):
            print("Creating checkpoints directory")
            os.makedirs("./checkpoints")

        sys.path.append("./checkpoints")

        url_w2v = "https://dl.fbaipublicfiles.com/fairseq/wav2vec/wav2vec_small.pt"
        w2v_path = "./checkpoints/wav2vec_small.pt"
        if not os.path.isfile(w2v_path):
            print("Downloading wav2vec 2.0 started")
            urlretrieve(url_w2v, w2v_path)
            print("wav2vec 2.0 download completed")

        model = NORESQA(
            output=40, output2=40, metric_type=metric_type, config_path=w2v_path
        )

        # Loading checkpoint
        if metric_type == 0:
            model_checkpoint_path = "../tools/Noresqa/models/model_noresqa.pth"
            state = torch.load(model_checkpoint_path, map_location="cpu")["state_base"]
        elif metric_type == 1:
            model_checkpoint_path = "../tools/Noresqa/models/model_noresqa_mos.pth"
            state = torch.load(model_checkpoint_path, map_location="cpu")["state_dict"]

        pretrained_dict = {}
        for k, v in state.items():
            if "module" in k:
                pretrained_dict[k.replace("module.", "")] = v
            else:
                pretrained_dict[k] = v
        model_dict = model.state_dict()
        model_dict.update(pretrained_dict)
        model.load_state_dict(pretrained_dict)

        # change device as needed
        model.to(device)
        model.eval()

        sfmax = nn.Softmax(dim=1)

    else:
        raise NotImplementedError

    return model


def noresqa_metric(model, gt_x, pred_x, fs, metric_type=1, device="cpu"):
    # NOTE(hyejin): only work for 16000 Hz
    nmr_feat, test_feat = feats_loading(pred_x, gt_x, noresqa_or_noresqaMOS=metric_type)
    test_feat = torch.from_numpy(test_feat).float().to(device).unsqueeze(0)
    nmr_feat = torch.from_numpy(nmr_feat).float().to(device).unsqueeze(0)

    with torch.no_grad():
        if metric_type == 0:
            noresqa_pout, noresqa_qout = model_prediction_noresqa(
                test_feat, nmr_feat, model
            )
            return {"noresqa_score": noresqa_pout}
        elif metric_type == 1:
            mos_score = model_prediction_noresqa_mos(test_feat, nmr_feat, model)
            return {"noresqa_score": mos_score}


if __name__ == "__main__":
    a = np.random.random(16000)
    b = np.random.random(16000)
    model = noresqa_model_setup(use_gpu=True)
    print("metrics: {}".format(noresqa_metric(model, a, b, 16000)))

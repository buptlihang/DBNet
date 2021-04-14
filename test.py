import sys

from deepvac.syszux_deepvac import Deepvac
from deepvac.syszux_loader import OsWalkDataset
from deepvac.syszux_log import LOG

import torch
import torchvision
import torch.utils.data as data
from torch.utils.data import DataLoader

from modules.utils import SegDetectorRepresenter
from modules.model_db import Resnet18DB

import time
import cv2
import os
import numpy as np
from PIL import Image

class DBDataset(OsWalkDataset):
    def __init__(self, config):
        super(DBDataset, self).__init__(config)
        self.long_size = config.long_size
    
    def scale(self, img):
        h, w = img.shape[0:2]
        scale = self.long_size * 1.0 / max(h, w)
        h, w = int(h*scale), int(w*scale)
        h += h%4
        w += w%4
        img = cv2.resize(img, (w, h))
        return img

    def __getitem__(self, idx):
        img = super(DBDataset, self).__getitem__(idx)

        img = img[:, :, [2, 1, 0]]
        scaled_img = self.scale(img)
        scaled_img = Image.fromarray(scaled_img)
        scaled_img = scaled_img.convert('RGB')
        scaled_img = transforms.ToTensor()(scaled_img)
        scaled_img = transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])(scaled_img)
        return scaled_img

class DeepvacDBTest(Deepvac):
    def __init__(self, deepvac_config):
        super(DeepvacDBTest,self).__init__(deepvac_config)
        if len(sys.argv) != 1:
            assert len(sys.argv)==2, 'You can only pass a image path !'
            LOG.logI('Find image: {}'.format(sys.argv[1]))
            self.conf.test.use_fileline = False
            self.conf.test.image_path = sys.argv[1]
        self.initTestLoader()
        self.post_process = SegDetectorRepresenter()
        self.is_output_polygon = True

    def initNetWithCode(self):
        if self.conf.train.arch == "resnet18":
            self.net = Resnet18DB()
        elif self.conf.test.arch == "mv3":
            self.net = Mobilenetv3DB()

        self.net.to(self.device)

    def report(self):
        for idx, (org_img, img, labels) in enumerate(self.test_loader):
            LOG.logI('progress: %d / %d'%(idx, len(self.test_loader)))

            img = img.to(self.device)
            start_time = time.time()
            preds = self.net(img)
            if str(self.device).__contains__('cuda'):
                torch.cuda.synchronize(self.device)
            print(time.time()-start_time)

            box_list, score_list = self.post_process({'shape': [(org_img.shape[0], org_img.shape[1])]}, preds, is_output_polygon=self.is_output_polygon)
            box_list, score_list = box_list[0], score_list[0]
            if len(box_list) <=0:
                cv2.imwrite('output/vis/'+str(idx).zfill(3)+'.jpg', org_img)
                continue
                
            if is_output_polygon:
                idx = [x.sum() > 0 for x in box_list]
                box_list = [box_list[i] for i, v in enumerate(idx) if v]
                score_list = [score_list[i] for i, v in enumerate(idx) if v]
            else:
                idx = box_list.reshape(box_list.shape[0], -1).sum(axis=1) > 0
                box_list, score_list = box_list[idx], score_list[idx]

            for point in box_list:
                point = point.astype(int)
                cv2.polylines(org_img, [point], True, (0, 255, 0), 2)
            cv2.imwrite('output/vis/'+str(idx).zfill(3)+'.jpg', org_img)


    def process(self):
        self.report()

    def initTestLoader(self):
        self.test_dataset = DBDataset(self.conf.test)
        self.test_loader = DataLoader(
            dataset=self.test_dataset,
            batch_size=self.conf.test.batch_size,
            shuffle=self.conf.test.shuffle,
            num_workers=self.conf.workers,
            drop_last=True
        )


if __name__ == '__main__':
    from config import config as deepvac_config
    db = DeepvacDBTest(deepvac_config)
    input_tensor = torch.rand(1,3,640,640)
    db(input_tensor)
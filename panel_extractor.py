# stdlib
from os import makedirs
from os.path import basename, exists, join, splitext

import cv2
import numpy as np
from skimage import measure
# 3p
from tqdm import tqdm

# project
from text_detector.main_text_detector import TextDetector
from utils import get_files, load_image, save_file


class PanelExtractor:
    def __init__(self, just_contours=False, keep_text=False, min_pct_panel=2, max_pct_panel=90, paper_th=0.35):
        self.just_contours = just_contours
        self.keep_text = keep_text
        assert min_pct_panel < max_pct_panel, "Minimum percentage must be smaller than maximum percentage"
        self.min_panel = min_pct_panel / 100
        self.max_panel = max_pct_panel / 100
        self.paper_th = paper_th

        # Load text detector
        print('Load text detector ... ', end="")
        self.text_detector = TextDetector()
        print("Done!")

    def _generate_panel_blocks(self, img):
        img = img if len(img.shape) == 2 else img[:, :, 0]
        blur = cv2.GaussianBlur(img, (5, 5), 0)
        thresh = cv2.threshold(blur, 230, 255, cv2.THRESH_BINARY)[1]
        cv2.rectangle(thresh, (0, 0), tuple(img.shape[::-1]), (0, 0, 0), 10)
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(thresh, 4, cv2.CV_32S)
        ind = np.argsort(stats[:, 4], )[::-1][1]
        panel_block_mask = ((labels == ind) * 255).astype("uint8")
        return panel_block_mask

    def generate_contours(self, img):
        block_mask = self._generate_panel_blocks(img)
        cv2.rectangle(block_mask, (0, 0), tuple(block_mask.shape[::-1]), (255, 255, 255), 10)

        # detect contours
        contours, hierarchy = cv2.findContours(block_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        good_contours = []

        for c in contours:
            area = cv2.contourArea(c)
            img_area = img.shape[0] * img.shape[1]
            # print("img.shape[0]", img.shape[0])
            # print("img.shape[1]", img.shape[1])

            # if the contour is very small or very big, it's likely wrongly detected
            if area < (self.min_panel * img_area) or area > (self.max_panel * img_area):
                continue

            good_contours.append(self.c2j(c, img.shape[0], img.shape[1]))
        
        return good_contours

    def generate_panels(self, img):
        block_mask = self._generate_panel_blocks(img)
        cv2.rectangle(block_mask, (0, 0), tuple(block_mask.shape[::-1]), (255, 255, 255), 10)

        # detect contours
        contours, hierarchy = cv2.findContours(block_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        panels = []

        for i in range(len(contours)):
            area = cv2.contourArea(contours[i])
            img_area = img.shape[0] * img.shape[1]

            # if the contour is very small or very big, it's likely wrongly detected
            if area < (self.min_panel * img_area) or area > (self.max_panel * img_area):
                continue

            x, y, w, h = cv2.boundingRect(contours[i])
            # create panel mask
            panel_mask = np.ones_like(block_mask, "int32")
            cv2.fillPoly(panel_mask, [contours[i].astype("int32")], color=(0, 0, 0))
            panel_mask = panel_mask[y:y+h, x:x+w].copy()
            # apply panel mask
            panel = img[y:y+h, x:x+w].copy()
            panel[panel_mask == 1] = 255
            panels.append(panel)

        return panels

    def remove_text(self, imgs):
        # detect text
        res = self.text_detector.detect(imgs)

        print("Removing text ... ", end="")
        text_masks = []
        for i, (_, polys) in enumerate(res):
            mask_text = np.zeros_like(imgs[i], "int32")
            for poly in polys:
                cv2.fillPoly(mask_text, [poly.astype("int32")], color=(255, 255, 255))
            text_masks.append(mask_text)

        # self.get_speech_bubble_mask(imgs, text_masks)

        without_text = []
        for i, img in enumerate(imgs):
            img[text_masks[i] == 255] = 255
            without_text.append(img)
        print("Done!")

        return without_text

    def get_speech_bubble_mask(self, imgs, text_masks):
        bubble_masks = []
        for i, img in enumerate(imgs):
            # get connected components
            _, bw = cv2.threshold(img, 230, 255.0, cv2.THRESH_BINARY)
            all_labels = measure.label(bw, background=25000)

            # speech labels
            labels = np.unique(all_labels[text_masks[i] == 255])

            # buble mask
            bubble_masks.append(np.isin(all_labels, labels) * 255)

    def c2j(self, c, img_H, img_W):
        x, y, w, h = cv2.boundingRect(c)
        x=x/img_W*100
        y=y/img_H*100
        w=w/img_W*100
        h=h/img_H*100
        return {
            "x": x,
            "y": y,
            "width": w,
            "height": h,
            # "path": path
            "path": f"{x} {y}, {x+w} {y}, {x+w} {y+h}, {x} {y+h}, {x} {y}"
        }

    def extract(self, folder):
        print("Loading images ... ", end="")
        image_list, _, _ = get_files(folder)
        print("Done!")

        # # create panels dir
        # if not exists(join(folder, "panels")):
        #     makedirs(join(folder, "panels"))
        # folder = join(folder, "panels")

        # # remove images with paper texture, not well segmented
        # paperless_imgs = []
        # for img in tqdm(imgs, desc="Removing images with paper texture"):
        #     hist, bins = np.histogram(img.copy().ravel(), 256, [0, 256])
        #     if np.sum(hist[50:200]) / np.sum(hist) < self.paper_th:
        #         paperless_imgs.append(img)

        # # remove text from panels
        # if not self.keep_text:
        #     paperless_imgs = self.remove_text(paperless_imgs)

        pages = []
        for i in tqdm(sorted(image_list), desc="extracting panels"):
            img = load_image(i)
            
            if(not self.just_contours):
                panels = self.generate_panels(img)
                print(f"we have {len(panels)} panels")
                name, ext = splitext(basename(i))
                for j, panel in enumerate(panels):
                    cv2.imwrite(join(folder, f'{name}_{j}.{ext}'), panel)

            contours = self.generate_contours(img)
            pages.append({
                "page_index": i,
                "image": f"https://cdn.onepiecechapters.com/file/CDN-M-A-N/{basename(i)}",
                "panels": sorted(contours, key=lambda p: p["y"])
            })

        # save pages on disk as json
        _final = {
            "title": "",
            "author": [
            ],
            "tags": [
            ],
            "pageCount": len(pages),
            "pages": pages
        }
        # Directly from dictionary
        save_file(_final, 'output.json')

        return _final


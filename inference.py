from __future__ import print_function

import scipy.io as sio
from PIL import Image
import cv2
import tensorflow as tf
import numpy as np

from model import DeepLabResNetModel

IMG_MEAN = np.array((104.00698793, 116.66876762, 122.67891434), dtype=np.float32)

NUM_CLASSES = 27
COLOR_MAT_FP = 'color150.mat'


def decode_label_colours(mat_fp):
    mat = sio.loadmat(mat_fp)
    color_table = mat['colors']
    shape = color_table.shape
    color_list = [tuple(color_table[i]) for i in range(shape[0])]

    return color_list


def decode_labels(mask, num_images=1, num_classes=150):
    label_colours = decode_label_colours(COLOR_MAT_FP)

    n, h, w, c = mask.shape
    assert(n >= num_images), 'Batch size %d should be greater or equal than number of images to save %d.' % (n, num_images)
    outputs = np.zeros((num_images, h, w, 3), dtype=np.uint8)
    for i in range(num_images):
      img = Image.new('RGB', (len(mask[i, 0]), len(mask[i])))
      pixels = img.load()
      for j_, j in enumerate(mask[i, :, :, 0]):
          for k_, k in enumerate(j):
              if k < num_classes:
                  pixels[k_,j_] = label_colours[k]
      outputs[i] = np.array(img)
    return outputs



class App(object):
    def __init__(self):
        self.name = 'App'
        self.model_path = './model/'
        self.session = None
        self.loader = None
        self.ckpt = None
        self.net = None
        self.img_tf = None
        self.cap = None
        self.in_progress = False
        self.img_shape = 300
        self.input_feed_shape = (1, self.img_shape, self.img_shape, 3)

    def _tf_init(self):
        self.img_tf = tf.placeholder(dtype=tf.float32, shape=self.input_feed_shape)
        self.net = DeepLabResNetModel({'data': self.img_tf}, is_training=False, num_classes=NUM_CLASSES)
        self.config = tf.ConfigProto()
        self.config.gpu_options.allow_growth = True

    def _pre_process(self, frame):
        img_resized = cv2.resize(frame.copy(), (self.img_shape, self.img_shape))
        img_feed = np.array(img_resized, dtype=float)
        img_feed = np.expand_dims(img_feed, axis=0)
        return img_resized, img_feed

    def _load_trained_model(self, saver, sess, ckpt_path):
        saver.restore(sess, ckpt_path)
        print("Restored model parameters from {}".format(ckpt_path))

    def run(self):
        self._tf_init()

        self.cap = cv2.VideoCapture(0)
        while True:
            ret, frame = self.cap.read()
            if ret and (not self.in_progress):
                img_resized, img_feed = self._pre_process(frame)
                restore_var = tf.global_variables()
                raw_output = self.net.layers['fc_out']
                raw_output_up = tf.image.resize_bilinear(raw_output, tf.shape(img_resized)[0:2, ])
                raw_output_up = tf.argmax(raw_output_up, dimension=3)
                pred = tf.expand_dims(raw_output_up, dim=3)

                if not self.session:
                    self.session = tf.Session(config=self.config)
                    init = tf.global_variables_initializer()
                    self.session.run(init)

                # Load pre-trained model
                if self.ckpt is None:
                    self.ckpt = tf.train.get_checkpoint_state(self.model_path)
                    if self.ckpt and self.ckpt.model_checkpoint_path and (self.loader is None):
                        self.loader = tf.train.Saver(var_list=restore_var)
                        self._load_trained_model(self.loader, self.session, self.ckpt.model_checkpoint_path)
                    else:
                        print('No checkpoint file found. or loaded!')

                self.in_progress = True
                _ops = self.session.run(pred, feed_dict={self.img_tf: img_feed})
                self.in_progress = False
                msk = decode_labels(_ops, num_classes=NUM_CLASSES)
                cv2.imshow('mask', msk[0])

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        self.cap.release()
        cv2.destroyAllWindows()


def main():
    app = App()
    app.run()


if __name__ == '__main__':
    main()
# In[0]


# In[1]
get_ipython().run_line_magic('matplotlib', 'nbagg')
import numpy as np
import matplotlib.pyplot as plt
import time
import os
os.environ["CUDA_VISIBLE_DEVICES"]="0"
import tensorflow as tf
import pickle

import tensorflow.keras.backend as K
from model import TBPP384
from tbpp_prior import PriorUtil
from tbpp_data import InputGenerator
from tbpp_training import TBPPFocalLoss
from utils.model import load_weights
from utils.training import Logger

# In[2]
from tensorflow.python.client import device_lib
print(device_lib.list_local_devices())

# In[3]
from data_synthtext import GTUtility
with open('gt_util_synthtext_seglink.pkl', 'rb') as f:
    gt_util = pickle.load(f)

gt_util_train, gt_util_val = gt_util.split(0.9)

# In[4]
# TextBoxes++
K.clear_session()
model = TBPP384(softmax=False)
weights_path = None

experiment = 'tbpp384fl_synthtext'

# In[5]
prior_util = PriorUtil(model)

# In[6]
import json

# In[7]
from tensorflow.keras.utils import get_custom_objects
from utils.layers import Normalize

# In[8]
get_custom_objects().update({
    "Normalize": Normalize
})

# In[9]
with open("../model_params.json",'w') as f:
    f.write(model.to_json())

# In[10]
from tensorflow.keras.models import model_from_json

# In[11]
with open("../model_params.json",'r') as f:
    parameter_saved_model = model_from_json(f.read())

# In[12]
from multiprocessing import cpu_count
from tensorflow.keras.callbacks import ModelCheckpoint

# In[13]
epochs = 10
initial_epoch = 0
batch_size = 32

gen_train = InputGenerator(gt_util_train, prior_util, batch_size, model.image_size)
gen_val = InputGenerator(gt_util_val, prior_util, batch_size*4, model.image_size)

checkdir = './checkpoints/' + time.strftime('%Y%m%d%H%M') + '_' + experiment
if not os.path.exists(checkdir):
    os.makedirs(checkdir)

with open(checkdir+'/source.py','wb') as f:
    source = ''.join(['# In[%i]\n%s\n\n' % (i, In[i]) for i in range(len(In))])
    f.write(source.encode())

optim = tf.keras.optimizers.SGD(lr=1e-3, momentum=0.9, decay=0, nesterov=True)
# optim = tf.keras.optimizers.Adam(lr=1e-3, beta_1=0.9, beta_2=0.999, epsilon=0.001, decay=0.0)

# weight decay
regularizer = tf.keras.regularizers.l2(5e-4) # None if disabled
#regularizer = None
for l in model.layers:
    if l.__class__.__name__.startswith('Conv'):
        l.kernel_regularizer = regularizer

loss = TBPPFocalLoss(lambda_conf=10000.0, lambda_offsets=1.0)

model.compile(optimizer=optim, loss=loss.compute, metrics=loss.metrics)

callbacks = [
    ModelCheckpoint(checkdir+'/weights.{epoch:03d}.h5', 
                    verbose=1, save_weights_only=True),
    Logger(checkdir)
]

print(checkdir.split('/')[-1])
history = model.fit_generator(
        gen_train.generate(),
        epochs=epochs, 
        steps_per_epoch=int(gen_train.num_batches/4), 
        callbacks=callbacks,
        validation_data=gen_val.generate(), 
        validation_steps=int(gen_val.num_batches/4),
        workers=cpu_count(), 
        use_multiprocessing=True)


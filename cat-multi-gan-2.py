from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import utils
import traceback
import numpy as np
import tensorflow as tf
import models_mnist as models
import datetime
import my_utils
from functools import partial


""" param """
epoch = 100
batch_size = 100
lr = 2e-4
beta1 = 0.5
z_dim = 128
n_critic = 1 #
n_generator = 1
gan_type="cat-multi-gan"
dir="results/"+gan_type+"-"+datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


''' data '''
# keep = range(10)
keep = [1,3,5]
data_pool = my_utils.getMNISTDatapool(batch_size, keep=keep) #range -1 ~ 1
data_pool_2 =  my_utils.getMNISTDatapool(batch_size, [1])
data_pool_3 =  my_utils.getMNISTDatapool(batch_size, [3])
data_pool_4 =  my_utils.getMNISTDatapool(batch_size, [5])

""" graphs """
generator = partial(models.cat_generator_m, heads=3)
# generator = models.cat_generator_3heads
discriminator = partial(models.cat_discriminator,out_dim=len(keep))

generator_2 = models.ss_generator_2
discriminator_2 = models.ss_discriminator

optimizer = tf.train.AdamOptimizer

# inputs
real = tf.placeholder(tf.float32, shape=[None, 28, 28, 1])
real_ = tf.placeholder(tf.float32, shape=[None, 28, 28, 1])
real_2 = tf.placeholder(tf.float32, shape=[None, 28, 28, 1])
real_3 = tf.placeholder(tf.float32, shape=[None, 28, 28, 1])
random_z = tf.placeholder(tf.float32, shape=[None, z_dim])

#marginal entropy
def mar_entropy(y):
    # y1 = F.sum(y, axis=0) / batchsize
    # y2 = F.sum(-y1 * F.log(y1))
    # return y2
    y1 = tf.reduce_mean(y,axis=0)
    y2=tf.reduce_sum(-y1*tf.log(y1))
    return y2

#conditional entropy
def cond_entropy(y):
    # y1 = -y * F.log(y)
    # y2 = F.sum(y1) / batchsize
    # return y2
    y1=-y*tf.log(y)
    y2 = tf.reduce_sum(y1)/batch_size
    return y2



fake_set = generator(random_z, reuse=False)
fake = tf.concat(fake_set, 0)
real_y,_= discriminator(real, reuse=False)
fake_y,_ = discriminator(fake)

#discriminator loss
d_loss = -1 * (mar_entropy(real_y) - cond_entropy(real_y) + cond_entropy(fake_y))   # Equation (7) upper

#generator loss
g_loss = -mar_entropy(fake_y) + cond_entropy(fake_y)  # Equation (7) lower

#learner
learner_fake = generator_2(random_z, name="learner",reuse=False)
learner_logit = discriminator_2(learner_fake, name='discriminator_2', reuse=False)
learner_y, learner_logit_2 = discriminator(learner_fake)
r_logit = discriminator_2(real ,name='discriminator_2',)

D_loss_real = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(logits=r_logit, labels=tf.ones_like(r_logit)))
D_loss_fake = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(logits=learner_logit, labels=tf.zeros_like(learner_logit)))
onehot_labels_zero = tf.one_hot(indices=tf.zeros(batch_size, tf.int32), depth=4)
# l_loss = cond_entropy(learner_y) + mar_entropy(learner_y)
d_2_loss = D_loss_real + D_loss_fake
# l_loss = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(logits=learner_logit, labels=tf.ones_like(learner_logit)))\
#          + tf.reduce_mean(tf.losses.softmax_cross_entropy(logits=learner_logit_2, onehot_labels=onehot_labels_zero))
l_loss = cond_entropy(learner_y)\
+ tf.reduce_mean(tf.losses.softmax_cross_entropy(logits=learner_logit_2, onehot_labels=onehot_labels_zero))
# trainable variables for each network
T_vars = tf.trainable_variables()
d_var = [var for var in T_vars if var.name.startswith('discriminator')]
g_var = [var for var in T_vars if var.name.startswith('generator')]

d_2_var = [var for var in T_vars if var.name.startswith('discriminator_2')]
l_var = [var for var in T_vars if var.name.startswith('learner')]

# optims
global_step = tf.Variable(0, name='global_step',trainable=False)
d_step = optimizer(learning_rate=lr, beta1=beta1).minimize(d_loss, var_list=d_var, global_step=global_step)
g_step = optimizer(learning_rate=lr, beta1=beta1).minimize(g_loss, var_list=g_var)

d_2_step = optimizer(learning_rate=lr, beta1=beta1).minimize(d_2_loss, var_list=d_2_var)
l_step = optimizer(learning_rate=lr, beta1=beta1).minimize(l_loss, var_list=l_var)

""" train """
''' init '''
# session
gpu_options = tf.GPUOptions(per_process_gpu_memory_fraction=0.7)
sess = tf.InteractiveSession(config=tf.ConfigProto(gpu_options=gpu_options))

# saver
saver = tf.train.Saver(max_to_keep=5)
# summary writer
# Send summary statistics to TensorBoard
tf.summary.scalar('d_loss', d_loss)
tf.summary.scalar('g_loss', g_loss)
tf.summary.scalar('l_loss', l_loss)
# images_from_g = generator(random_z, training=False)[0]
# tf.summary.image('Generator_image', images_from_g, 12)
image_sets = generator(random_z, training=False)
# name_sets = []
for i in range(len(image_sets)):
    tf.summary.image('Generator_image_c%d'%i, image_sets[i], 12)

image_from_learner = generator_2(random_z, name="learner", training=False)
tf.summary.image('Generator_image_l', image_from_learner, 12)

p_1,_ = discriminator(real_, training=False)
p_2,_ = discriminator(real_2, training=False)
p_3,_ = discriminator(real_3, training=False)
predict_y_1 = tf.argmax(tf.reduce_mean(p_1, axis=0))
predict_y_2 = tf.argmax(tf.reduce_mean(p_2, axis=0))
predict_y_3 = tf.argmax(tf.reduce_mean(p_3, axis=0))

# predict_y_1 = tf.argmax(tf.reduce_mean(discriminator(real_, training=False), axis=0))
# predict_y_2 = tf.argmax(tf.reduce_mean(discriminator(real_2, training=False), axis=0))
# predict_y_3 = tf.argmax(tf.reduce_mean(discriminator(real_3, training=False), axis=0))

tf.summary.histogram('predict for 1', predict_y_1)
tf.summary.histogram('predict for 3', predict_y_2)
tf.summary.histogram('predict for 5', predict_y_3)

merged = tf.summary.merge_all()
logdir = dir+"/tensorboard"
writer = tf.summary.FileWriter(logdir, sess.graph)
print('Tensorboard dir: '+logdir)

''' initialization '''
sess.run(tf.global_variables_initializer())

''' train '''
batch_epoch = len(data_pool) // (batch_size * n_critic)
max_it = epoch * batch_epoch

def sample_once(it):
    rows = 10
    columns = 10
    feed = {random_z: np.random.normal(size=[rows * columns, z_dim])}
    list_of_generators = image_sets  # used for sampling images
    list_of_names = ['it%d-c%d.jpg' %(it,i) for i in range(len(image_sets))]
    save_dir = dir + "/sample_imgs"
    my_utils.sample_and_save(sess=sess, list_of_generators=list_of_generators, feed_dict=feed,
                             list_of_names=list_of_names, save_dir=save_dir)

def training(max_it, it_offset):
    print("Max iteration: " + str(max_it))
    # total_it = it_offset + max_it
    for it in range(it_offset, it_offset + max_it):
        real_ipt = (data_pool.batch('img')+1)/2.
        z_ipt = np.random.normal(size=[batch_size, z_dim])
        if it<5000:
            _ = sess.run([d_step], feed_dict={real: real_ipt, random_z: z_ipt})
            _ = sess.run([g_step], feed_dict={random_z: z_ipt})
        else:
            _ = sess.run([d_2_step], feed_dict={real: real_ipt, random_z: z_ipt})
            _ = sess.run([l_step], feed_dict={random_z: z_ipt})

        if it%10 == 0 :
            # real_ipt =
            # real_ipt_ =
            summary = sess.run(merged, feed_dict={real: (data_pool.batch('img')+1)/2.,
                                                  real_: (data_pool_2.batch('img')+1)/2.,
                                                  real_2:(data_pool_3.batch('img')+1)/2.,
                                                real_3:(data_pool_4.batch('img')+1)/2.,
                                                  random_z: np.random.normal(size=[batch_size, z_dim])})
            writer.add_summary(summary, it)

        if it%100 == 0:
            # real_ipt_ =
            y1, y2, y3, = sess.run([predict_y_1, predict_y_2, predict_y_3], feed_dict={
                                                real_: (data_pool_2.batch('img')+1)/2.,
                                                  real_2:(data_pool_3.batch('img')+1)/2.,
                                                real_3:(data_pool_4.batch('img')+1)/2.,})
            print(y1)
            print(y2)
            print(y3)
            print('-----')

            # for i,j,k in zip(y1,y2,y3):
            #     counts_1 = counts_2 = counts_3 = [0,0,0]
            #     counts_1[i] += 1
            #     counts_2[i] += 1
            #     counts_3[i] += 1
            #     print(counts_1)


    var = raw_input("Continue training for %d iterations?" % max_it)
    if var.lower() == 'y':
        sample_once(it_offset + max_it)
        print("Save sample images")
        training(max_it, it_offset + max_it)

total_it = 0
try:
    training(max_it,0)
    total_it = sess.run(global_step)
    print("Total iterations: "+str(total_it))
except Exception, e:
    traceback.print_exc()
finally:
    var = raw_input("Save sample images?")
    if var.lower() == 'y':
        sample_once(total_it)
    # save checkpoint
    save_path = saver.save(sess, dir+"/checkpoint/model.ckpt")
    print("Model saved in path: %s" % save_path)
    print(" [*] Close main session!")
    sess.close()

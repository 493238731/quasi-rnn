import tensorflow as tf
from qrnn import QRNN_layer
from tensorflow.contrib.layers import xavier_initializer
from tensorflow.contrib.layers import flatten, fully_connected


def scalar_summary(name, x):
    try:
        summ = tf.summary.scalar(name, x)
    except AttributeError:
        summ = tf.scalar_summary(name, x)
    return summ

def histogram_summary(name, x):
    try:
        summ = tf.summary.histogram(name, x)
    except AttributeError:
        summ = tf.histogram_summary(name, x)
    return summ

class QRNN_lm(object):
    """ Implement the Language Model from https://arxiv.org/abs/1611.01576 """
    def __init__(self, args):
        self.batch_size = args.batch_size
        self.seq_len = args.seq_len
        self.vocab_size = args.vocab_size
        self.emb_dim = args.emb_dim
        self.qrnn_size = args.qrnn_size
        self.qrnn_layers = args.qrnn_layers
        self.words_in = tf.placeholder(tf.int32, [self.batch_size,
                                                  self.seq_len])
        self.words_gtruth = tf.placeholder(tf.int32, [self.batch_size,
                                                      self.seq_len])

        self.logits, self.output = self.inference()
        self.loss = self.lm_loss(self.logits, self.words_gtruth)
        # set up optimizer
        self.lr = tf.Variable(args.learning_rate, trainable=False)
        self.lr_summary = scalar_summary('lr', self.lr)
        tvars = tf.trainable_variables()
        grads, _ = tf.clip_by_global_norm(tf.gradients(self.loss, tvars),
                                          args.grad_clip)
        self.opt = tf.train.GradientDescentOptimizer(self.lr)
        self.train_op = self.opt.apply_gradients(zip(grads, tvars))

    def inference(self):
        words_in = self.words_in
        embeddings = None
        with tf.variable_scope('QRNN_LM'):
            word_W = tf.get_variable("word_W",
                                     [self.vocab_size,
                                      self.emb_dim])
            words = tf.split(1, self.seq_len, tf.expand_dims(words_in, -1))
            # print('len of words: ', len(words))
            for word_idx in words:
                word_embed = tf.nn.embedding_lookup(word_W, word_idx)
                # print('word embed shape: ', word_embed.get_shape().as_list())
                if embeddings is None:
                    embeddings = tf.squeeze(word_embed, [1])
                else:
                    embeddings = tf.concat(1, [embeddings,
                                           tf.squeeze(word_embed, [1])])
            print('embeddings shape: ', embeddings.get_shape().as_list())
            qrnn_h = embeddings
            for qrnn_l in range(self.qrnn_layers):
                qrnn_ = QRNN_layer(qrnn_h, self.qrnn_size, pool_type='f',
                                   name='QRNN_layer{}'.format(qrnn_l))
                qrnn_h = qrnn_.h
                print('qrnn_h{} shape: {}'.format(qrnn_l, qrnn_h.get_shape().as_list()))

            qrnn_h_f = tf.reshape(qrnn_h, [-1, self.qrnn_size])
            logits = fully_connected(qrnn_h_f,
                                     self.vocab_size,
                                     weights_initializer=xavier_initializer(),
                                     biases_initializer=tf.constant_initializer(0.),
                                     scope='output_softmax')
            output = tf.nn.softmax(logits)
            return logits, output

    def lm_loss(self, logits, words_gtruth):
        f_words_gtruth = tf.reshape(words_gtruth,
                                    [self.batch_size * self.seq_len])
        loss =  tf.nn.sparse_softmax_cross_entropy_with_logits(logits,
                                                               f_words_gtruth)
        return tf.reduce_mean(loss)

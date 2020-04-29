import tensorflow as tf
from model import make_vgg
import hyperparameters as hp
import cv2

# refactored functions to work with both images and video
image_height = hp.img_height
image_width = hp.img_width

content_layers = [14]
style_layers = [2, 5, 8, 13, 18]

model = make_vgg(image_height, image_width)

def preprocess_image(image_path):
	image = tf.io.read_file(image_path)
	image = tf.image.decode_image(image, channels=3, dtype=tf.float32)
	image = tf.image.resize(image, (image_height, image_width), antialias=True)
	image = tf.image.convert_image_dtype(image, tf.uint8)
	image = tf.expand_dims(image, 0)
	image = tf.keras.applications.imagenet_utils.preprocess_input(image)
	image = tf.image.convert_image_dtype(image, tf.float32)
	return image

def initialize_stylized():
	# Output stylized image
	output_stylized_img = tf.random.normal((1, image_height, image_width, 3), mean=0.5)
	output_stylized_img = tf.clip_by_value(output_stylized_img, clip_value_min=0.0, clip_value_max=1.0)
	output_stylized_img = tf.Variable(output_stylized_img)
	return output_stylized_img

def stylize_frame(content, style, initial_stylized, precomputed_style_grams=None, use_temporal_loss=False, frames=None):
	"""Generates a stylized still image frame using the content from content, the
	style from style. The stylized image is initialized as the inputted stylized image.
	We can also pass in stylized feature maps rather than a stylized image, in which
	case we do not need to recompute the feature maps. We include temporal loss in
	total loss if use_temporal_loss is True.

	Arguments:
		- content: the content target image, already processed (tensorflow variable)
		- style: the style target image, already processed (tensorflow variable)
		- initial_stylized: the initialized value of our stylized image, we will optimize
					starting from this value. If stylizing an image, we pass in
					whitenoise. If stylizing a frame of a video, we pass in
					whitenoise for the first frame, and the previous stylized frame
					for every subsequent frame.
		- precomputed_style_grams: when stylizing a video, we do not want to recompute the
					style feature maps for the style target in every frame.
					instead, we should compute once and then pass in the
					feature map gram matrices to this function for every frame
		- use_temporal_loss: whether or not to include temporal loss in the total
					loss calculation
		- frames: a list [prev_frame, curr_frame, next_frame]
	"""
	# the previous stylized frame
	previous_stylized = tf.identity(initial_stylized)

	# TODO: temporal weights mask
	weights_mask = []
	if use_temporal_loss:
		weights_mask = compute_disocclusion_mask(frames[0], frames[1], frames[2])


	stylized = initial_stylized
	# we will compare stylized responses against these at each epoch to calculate loss
	content_feature_maps = compute_all_feature_maps(content, content_layers)
	style_feature_grams = precomputed_style_grams
	# check if we need to compute style target style responses now or if already computed
	if style_feature_grams is None:
		style_feature_grams = features_to_grams(compute_all_feature_maps(style, style_layers))

	# optimize loss
	optimizer = tf.optimizers.Adam(learning_rate=hp.learning_rate)
	# Optimizes images to minimize loss between input content image/input style image and output stylized image
	num_epochs = hp.epoch_num
	for e in range(num_epochs):
		# Watches loss computation (output_stylized_img watched by default since declared as variable)
		with tf.GradientTape() as tape:
			# compute stylized features response to content and style layers
			stylized_content_features = compute_all_feature_maps(stylized, content_layers)
			stylized_style_feature_grams = features_to_grams(compute_all_feature_maps(stylized, style_layers))
			# calculate loss
			loss = get_total_loss(content_feature_maps, style_feature_grams, stylized_content_features, stylized_style_feature_grams)
		if e % 10 == 0:
			print("Epoch " + str(e) + " Loss: " + str(loss))
		# calculate gradient of loss with respect to the stylized image (a variable)
		grad = tape.gradient(loss, stylized)
		# Applies this gradient to the image
		optimizer.apply_gradients([(grad, stylized)])
		# Clips image from 0-1, assigns gradient applied image to image variable
		stylized.assign(tf.clip_by_value(stylized, clip_value_min=0.0, clip_value_max=1.0))

	# Removes batch axis, converts image from BGR back to RGB, saves stylized image as "output.jpg" in same directory
	output_image = tf.reverse(tf.squeeze(stylized), axis=[-1]).numpy()
	tf.keras.preprocessing.image.save_img('output.jpg', output_image)

# computes list of feature map responses by passing image through network
# up until each layer in layers
def compute_all_feature_maps(image, layers):
	maps = []
	for layer in layers:
		feat = compute_feature_map(image, layer)
		maps.append(feat)
	return maps

# Feeds image through portion of VGG (depending on content or style model)
# Returns feature map for that image
def compute_feature_map(img, max_layer):
	img_copy = img
	for l in range(max_layer):
		curr_layer = model.get_layer(index=l)
		img_copy = curr_layer(img_copy)
	return img_copy

def features_to_grams(feature_maps):
	grams = []
	for i in range(len(feature_maps)):
		g = compute_feature_map_gram(feature_maps[i])
		grams.append(g)
	return grams
	
# Vectorizes feature map, then computes its Gram matrix
def compute_feature_map_gram(feature_map):
	depth = feature_map.shape[3]
	b = tf.reshape(tf.squeeze(feature_map) , [-1, depth])
	a = tf.transpose(b)
	return tf.linalg.matmul(a, b)


# Gets content loss, style loss, then multiplies them by corresponding weights to get total loss
# (Weights are different than the paper, but after lots of trial and error these seem to work well)
#       They might be different due to the different optimizer?
def get_total_loss(content_features, style_feature_grams, stylized_content_features, 
					stylized_style_feature_grams, use_temporal_loss=False, previous_stylized=None,
					weights_mask=None):
	content_loss = layered_mean_squared_error(content_features, stylized_content_features)
	style_loss = layered_mean_squared_error(style_feature_grams, stylized_style_feature_grams)
	total_loss = hp.content_loss_weight * content_loss + hp.style_loss_weight * style_loss
	# add temporal loss if applicable
	if use_temporal_loss:
		temporal_loss = get_temporal_loss(previous_stylized, stylized, weights_mask)
		total_loss += hp.temporal_loss_weight * temporal_loss
	return total_loss

def layered_mean_squared_error(source_features, generated_features):
	total_loss = tf.constant(0.0)
	for i in range(len(source_features)):
		layer_loss = tf.keras.losses.MeanSquaredError()(source_features[i], generated_features[i])
		total_loss += layer_loss
	return total_loss


# TEMPORAL STUFF

def compute_disocclusion_mask(prev_frame, curr_frame, next_frame):
	# TODO: implement weights matrix where value is 0 if pixel is disoccluded and
	# 1 otherwise?

	return curr_frame


def get_temporal_loss(previous_stylized, current_stylized, weights_mask):
	
	# TODO: implement temporal loss between 

	return 0

def get_flow_vectors(frame_1, frame_2):

	# #TODO: implement Gunner Farneback algorithm using OpenCV

	# print(frame_1.numpy().shape)

	# frame_1 = frame_1.numpy()
	# frame_2 = frame_2.numpy()

    # frame_1 = np.reshape(frame_1, (frame_1.shape[1], frame_1.shape[2], frame_1.shape[3]))
    # frame_2 = np.reshape(frame_2, (frame_2.shape[1], frame_2.shape[2], frame_2.shape[3]))

    # frame_1 = cv2.cvtColor(frame_1,cv2.COLOR_BGR2GRAY)
    # frame_2 = cv2.cvtColor(frame_2,cv2.COLOR_BGR2GRAY)


    # #Calculate Flow
    # flow = cv2.calcOpticalFlowFarneback(frame_1,frame_2, None, 0.5, 3, 15, 3, 5, 1.2, 0)

    # return flow
	return None


def apply_optical_flow(frame, next_frame, stylized_frame):

	# # TODO: apply optical flow from frame to next frame onto stylized frame

	# flow = get_flow_vectors(frame, next_frame)

	# h, w = flow.shape[:2]
    # flow = -flow
    # flow[:,:,0] += np.arange(w)
    # flow[:,:,1] += np.arange(h)[:,np.newaxis]
    # res = cv2.remap(img, flow, None, cv2.INTER_LINEAR)

	# return
	return None


def stylize_image(content_path, style_path):
	content = preprocess_image(content_path)
	style = preprocess_image(style_path)
	stylized = initialize_stylized()
	stylize_frame(content, style, stylized)


def stylize_video(video_path, style_path):
	num_frames = 100
	# starts uninitialized because there is no previous stylized frame at beginning
	initial_stylized = initialize_stylized()
	style = tf.Variable()
	# preprocessing 
	for f in range(num_frames):
		content = tf.Variable()
		stylized = initial_stylized
		# stylize img
		stylized = stylize_frame(content, style, stylized)
		# update previous stylized frame to the frame we just stylized with optical flow applied
		
		# TODO: MAKE THIS WORK f, f+1, just numbers
		initial_stylized = apply_optical_flow(f, f+1, stylized)

content_path = tf.keras.utils.get_file('Labrador.jpg', 'https://storage.googleapis.com/download.tensorflow.org/example_images/YellowLabradorLooking_new.jpg')
style_path = tf.keras.utils.get_file('Starry_Night.jpg','https://i.ibb.co/LvGcMQd/606px-Van-Gogh-Starry-Night-Google-Art-Project.jpg')

content = preprocess_image(content_path)
style = preprocess_image(style_path)
stylized = initialize_stylized()
stylize_frame(content, style, stylized)


# Uncomment this if running in Colab:
# from google.colab import files
# files.download('output.jpg')
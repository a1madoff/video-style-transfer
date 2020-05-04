
import os
import argparse
import tensorflow as tf
import hyperparameters as hp
from stylize import stylize_image
from stylize import stylize_video

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
data_folder = os.path.dirname(__file__) + '../data/'
framerate = 30
video_path = "./../data/content/video/elephant.mp4"
# # style_path = tf.keras.utils.get_file('kandinsky.jpg','https://storage.googleapis.com/download.tensorflow.org/example_images/Vassily_Kandinsky%2C_1913_-_Composition_7.jpg')

# # content_path = tf.keras.utils.get_file('Labrador.jpg', 'https://storage.googleapis.com/download.tensorflow.org/example_images/YellowLabradorLooking_new.jpg')

image_path = "./../data/content/images/Labrador.jpg"
style_path = "./../data/style/Starry_Night.jpg"




def parse_args():
    """ Perform command-line argument parsing. """

    parser = argparse.ArgumentParser(
        description="Style transfer!")
    parser.add_argument(
        '--video',
        required=False,
        action='store_true',
        help='''are you loading in a video?''')
    parser.add_argument(
        '--image',
        required=False,
        action='store_true',
        help='''are you loading in an image?''')
    parser.add_argument(
        '--both',
        required=False,
        action="store_true",
        help='both short and long term consistency.')   
    parser.add_argument(
        '--short',
        required=False,
        action="store_true",
        help='enforce short term consistency.')
    parser.add_argument(
        '--num_epochs',
        required=False,
        type=int,
        default=hp.num_epochs,
        help='hyperparameter number of epochs.')                           
    parser.add_argument(
        '--learning_rate',
        required=False,
        type=float,
        default=hp.learning_rate,
        help='hp learning rate.')       
    parser.add_argument(
        '--content_weight',
        required=False,
        type=float,
        default=hp.content_loss_weight,
        help='adjust content weight (high).')
    parser.add_argument(
        '--style_weight',
        required=False,
        type=float,
        default=hp.style_loss_weight,
        help='adjust style weight (low).')
    parser.add_argument(
        '--temporal_weight',
        required=False,
        type=float,
        default=hp.temporal_loss_weight,
        help='adjust temporal loss weight.')
    parser.add_argument(
        '--style',
        required=False,
        type=str,
        default=style_path,
        help='style file.')
    parser.add_argument(
        '--content',
        required=False,
        type=str,
        default=image_path,
        help='content file.')                                             
    return parser.parse_args()

def main():
    #get image paths
    #calling img_stylize or vid_stylize to stylize the content
    if (ARGS.content):
        video_path = ARGS.content
        image_path = ARGS.content
    if ARGS.image and not(ARGS.video):
        print("image style")
        stylize_image(image_path, ARGS.style, ARGS.content_weight, ARGS.style_weight, ARGS.temporal_weight, ARGS.learning_rate, ARGS.num_epochs)
    if ARGS.video and not(ARGS.image):
        print("video style") 
        stylize_video(video_path, ARGS.style, ARGS.fps , ARGS.content_weight, ARGS.style_weight, ARGS.temporal_weight, ARGS.num_epochs, ARGS.learning_rate)

        
    
        
    

#image vs. video, style, content, temporal loss (none, short, both)
#global arguments
ARGS = parse_args()


#run main
main()
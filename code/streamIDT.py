# imports
import os
import torch
from torchvision.utils import save_image, make_grid
from qsketch.sketch import add_sketch_arguments, add_data_arguments
import numpy as np
from qsketch import sketch
from IDT import streamIDT, add_IDT_arguments
import argparse
import matplotlib.pyplot as plt

plt.ion()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=
                                     'Performs iterative distribution transfer'
                                     ' with sliced Wasserstein flow.')
    parser = add_data_arguments(parser)
    parser = add_sketch_arguments(parser)
    parser = add_IDT_arguments(parser)

    parser.add_argument("--output",
                        help="If provided, save the generated samples to "
                             "this file path after transportation. Be sure "
                             "to add a `stop` parameter for the transport "
                             "to terminate for this to happen.")
    parser.add_argument("--plot",
                        help="Flag indicating whether or not to plot samples",
                        action="store_true")
    parser.add_argument("--plot_target",
                        help="Samples from the target. Same constraints as "
                             "the `dataset` argument.")
    parser.add_argument("--stop",
                        help="Number of sketches done before stopping. "
                             "A negative value means endless transport.",
                        type=int,
                        default=-1)
    parser.add_argument("--plot_dir",
                        help="Output directory for saving the plots",
                        default="./samples")

    args = parser.parse_args()

    if args.dataset is None:
        raise ValueError("Need either a sketch file or a dataset. "
                         "Aborting.")
    if args.root_data_dir is None:
        args.root_data_dir = 'data/'+args.dataset
    data_loader = sketch.load_data(args.dataset, None, args.root_data_dir,
                                   args.img_size, args.memory_usage)
    data_dim = int(np.prod(data_loader.dataset[0][0].shape))

    import ipdb; ipdb.set_trace()
    # prepare the projectors
    ProjectorsClass = getattr(sketch, args.projectors)
    projectors = ProjectorsClass(np.inf, data_dim)

    # prepare the sketch iterator
    sketches = sketch.SketchIterator(data_loader, projectors, args.batchsize,
                                     args.num_quantiles, 0, args.stop)

    # get the initial samples
    if args.initial_samples is None:
        # If no samples are provided, generate random ones
        samples = np.random.randn(args.num_samples, args.input_dim)*1e-10
        # if required, transform the samples to the data_dim
        if args.input_dim != data_dim:
            np.random.seed(0)
            up_sampling = np.random.randn(args.input_dim, data_dim)
            samples = np.dot(samples, up_sampling)
    else:
        # if a samples file is given, load it
        samples = np.load(args.initial_samples)
        if len(samples.shape) != 2 or samples.shape[1] != data_dim:
            raise ValueError('Samples in %s do not have the right shape. '
                             'They should be num_samples x %d for this '
                             'sketch file.' % (args.initial_samples, data_dim))

    if args.plot_target is not None:
        # just handle numpy arrays now
        target_samples = sketch.load_data(args.plot_target, None).dataset.data
        data_dim = target_samples.shape[1]

        ntarget = min(10000, target_samples.shape[0])
        target_samples = target_samples[:ntarget]
        axis_lim = [[v.min(), v.max()] for v in target_samples.T]
    if args.plot:
        if not os.path.exists(args.plot_dir):
            os.mkdir(args.plot_dir)

        def plot_function(samples, epoch, index):
            data_dim = samples.shape[-1]
            image = False

            # try to identify if it's an image or not
            if data_dim > 700:
                # if the data dimension is large: probably an image.
                square_dim_bw = np.sqrt(data_dim)
                square_dim_col = np.sqrt(data_dim/3)
                if not (square_dim_col % 1):  # check monochrome
                    image = True
                    nchan = 3
                    img_dim = int(square_dim_col)
                elif not (square_dim_bw % 1):  # check color
                    image = True
                    nchan = 1
                    img_dim = int(square_dim_bw)

            if not image:
                # no image: just plot second data dimension vs first one
                plt.figure(1, figsize=(8, 8))
                plt.clf()
                if args.plot_target is not None:
                    plt.plot(target_samples[:, 0], target_samples[:, 1], 'or')
                plt.plot(samples[:, 0], samples[:, 1], 'ob')
                plt.xlim(axis_lim[0])
                plt.ylim(axis_lim[1])
                plt.grid(True)
                plt.title('epoch %d, sketches %d'
                          % (epoch, index+1))
                plt.pause(0.05)
                plt.show()
                return

            # it's an image, output a grid of samples
            [num_samples, data_dim] = samples.shape
            samples = samples[:min(104, num_samples)]
            num_samples = samples.shape[0]

            samples = np.reshape(samples,
                                 [num_samples, nchan, img_dim, img_dim])
            pic = make_grid(torch.Tensor(samples),
                            nrow=8, padding=2, normalize=True, scale_each=True)
            save_image(pic, '{}/image_{}_{}.png'.format(args.plot_dir, epoch,
                                                        index+1))
    else:
        plot_function = None


    samples = streamIDT(sketches, samples, args.stepsize, args.reg,
                        plot_function)

    if args.write is not None:
        np.save(args.write, samples)

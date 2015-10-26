IPython extension to run code remotely and return some results

This extension provides line and cell
[magics](http://ipython.readthedocs.org/en/stable/interactive/magics.html) for
IPython to run code on other python kernels, and return requested variables.
These kernels can be remote kernels (probably best set up with
[`remote_ikernel`](https://bitbucket.org/tdaff/remote_ikernel/)), providing a
simple way to run code on one or more remote systems from a local IPython
instance.

The `remote_ikernel` module is very useful for seamlessly running Jupyter
notebooks on a local computer, but connecting to a remote system to actually do
the calculations.  However, in some cases, it's useful to be able to run most
of the calculations on the local computer, but get quick results from remote
systems when transferring all the data needed for the calculation would take
too long, or when results from several remote systems need to be combined into
one analysis.  This module attempts to fill that gap by running a single line
of code, an entire cell, or even multiple cells on remote kernels and returning
the requested data.


# Installation

To install this extension, the easiest method is to use `pip`:

    pip install https://github.com/moble/remote_exec/archive/master.zip

If that doesn't work, you can download this repository, and run `python install
setup.py`.

Now you have to load it into your IPython session.  If you just want to try out
the extension, you can load it just once by running

    %load_ext remote_exec

in your IPython session.  To load the extension automatically every time you
run IPython, add something like the following to your `ipython_config.py` file:

    c.InteractiveShellApp.extensions = ['remote_exec',]

You can find this file's directory by doing `ipython profile locate` on the
command line.


# Use

To run, make a cell something like the following:

    %%remote_exec -k kernel1,kernel2 -o x,y
    import numpy as np
    x = np.linspace(0,6)
    y = np.sin(x)

Here, `kernel1,kernel2` lists some kernels that ipython knows how to run, and
are the names of variables exported to the local namespace of the notebook
where this is called.  Each of these `kernelN` variables will contain members
`x` and `y` in this example, which will be the data as computed by those
kernels.  Now, in another cell, we can plot the results as

    plt.plot(kernel1.x, kernel1.y, label='kernel1')
    plt.plot(kernel2.x, kernel2.y+0.1, label='kernel2')
    plt.legend()

Of course, this example is fairly silly because the same thing is done on each
kernel, and could have been done just as easily on the local kernel.  More
interesting examples will use files that are only present on the remote
systems, but are too big to transfer.  Because of this, it is possible to
specify the working directory for each system, as in something like this:

    %%remote_exec -k kernel1:/path/on/system1,kernel2:/different/path -o x,y
    ...

It is also possible to specify slightly different code for different kernels.
In this case, you need to create a dictionary mapping the kernel names to a
string containing the desired code.  For example, you might want to analyze
different filenames on different systems.  You first define the dictionary

    filenames = {'kernel1': 'file1.txt', 'kernel2': 'file2.txt'}

Now, you can run code that will substitute those input values at the
appropriate times:

    %%remote_exec -k kernel1:/path/on/system1,kernel2:/different/path -o x,y -i filenames
    import numpy as np
    x, y = np.loadtxt("{filenames}").T

More input variables can be listed separated by commas.  Just remember that the
variable name must be surrounded by braces to be substituted, and that the
substitution will be exact.  In this case, `np.loadtxt` needs a string, while
`{filenames}` will be substituted with the value of the string without the
quotes, so we need to write the code with the quotes.  Of course, we could have
also included the quotes in the `filenames` variables, as in `'"file1.txt"'`.

Note that the names `kernel1` and `kernel2` need only match a subset of your
kernel's full name, so that `kernel1` could start a kernel that is actually
named `python_kernel1_myserver`.  The only stipulation is that the name you
provide must match exactly one full kernel name, which may not be what is
displayed in the Jupyter notebook's list of kernels.  To find the possible full
kernel names, run `jupyter-kernelspec list` from the command line.  Reasonably
similar versions of python are needed on each system.  In particular, the data
is pickled on the remote systems, and unpickled on the local system.  This
seems to require that all systems run either python 2 or python 3 -- no mixing.

Also note that the kernels are persistent within your local IPython session,
which means that the same kernels can be used in different cells, so that you
can reuse data or imports or whatever.  The remote kernels are all killed
whenever your main IPython kernel exits.  It is also possible to manually
shutdown the kernels using the `-s` option.  The kernels will still exist until
the main IPython kernel exits, but they will not be running unless they are
asked to run code again, in which case they automatically restart.  Thus,
adding `-s` to any call with code is a handy way to restart the kernel before
the code is run.

Finally, it is also possible to use this as a line magic, by putting the code
at the end of the line -- though this is presumably only useful for initial
imports or something comparable:

    %remote_exec -k kernel1,kernel2 import sys, numpy, scri

However, note that in all cases, `pickle` and `os` are imported automatically
because they are necessary for transporting the output variables back to your
local kernel.

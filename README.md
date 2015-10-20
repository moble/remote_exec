IPython extension to run code remotely and return some results

This extension provides line and cell
[magics](http://ipython.readthedocs.org/en/stable/interactive/magics.html) to
run code on other python kernels, and return requested variables.  These
kernels can be remote kernels (probably best set up with
[`remote_ikernel`](https://bitbucket.org/tdaff/remote_ikernel/)), providing a
simple way to run code on one or more remote systems from a local IPython
instance.

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

    filenames = {'kernel1': '"file1.txt"', 'kernel2': '"file2.txt"'}

Now, you can run code that will substitute those input values at the
appropriate times:

    %%remote_exec -k kernel1:/path/on/system1,kernel2:/different/path -o x,y -i filename
    import numpy as np
    x, y = np.loadtxt({filename})

More input variables can be listed separated by commas.  Just remember that the
variable name must be surrounded by braces to be substituted, and that the
substitution will be exact, which is why we included the quotes in
`'"file1.txt"'`, etc.

Also note that the kernels are persistent, which means that the same kernels
will be used in different notebook cells, so that you can reuse data or imports
or whatever.

Finally, it is also possible to use this as a line magic, but putting the code
at the end of the line -- though this is presumably only useful for initial
imports or something comparable:

    %remote_exec -k kernel1,kernel2 import sys, numpy, scri

However, note that in all cases, `pickle` and `os` are imported automatically
because they are necessary for transporting the output variables back to your
local kernel.

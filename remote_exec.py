# coding: utf-8
"""Notebook extension to run ipython code remotely, and get output

This is most useful as a cell magic, though it is available as a line magic,
too.  To run, make a cell something like the following:

    %%remote_exec -k kernel1,kernel2 -o x,y
    import numpy as np
    x = np.linspace(0,6)
    y = np.sin(x)

Here, `kernel1,kernel2` lists some kernels that ipython knows how to run, and
are the names of variables exported to the local namespace of the notebook
where this is called.  Now, in another cell, we can plot the results as

    plt.plot(kernel1.x, kernel1.y, label='kernel1')
    plt.plot(kernel2.x, kernel2.y, label='kernel2')
    plt.legend()

It is also possible to use `%remote_exec` as a line magic.

"""


from IPython.core.magic import (Magics, magics_class, line_cell_magic, needs_local_scope)
from IPython.core.magic_arguments import (
    argument, magic_arguments, parse_argstring, argument_group
)


class RemoteKernel(object):

    def __init__(self, kernel_manager, kernel_name):
        # Locate the best match for the kernel_name in the list of possible
        # kernel names
        from jupyter_client.kernelspec import KernelSpecManager
        kernelspecs = list(KernelSpecManager().find_kernel_specs().keys())
        if kernel_name in kernelspecs:  # perfect match
            kernel_full_name = kernel_name
        elif sum(kernel_name in kernelspec for kernelspec in kernelspecs) == 1:  # exact substring of 1
            kernel_full_name = kernelspecs[[kernel_name in kernelspec for kernelspec in kernelspecs].index(True)]
        else:
            import re
            regex = re.compile(kernel_name.replace('_', '.*?'), re.I)
            matches = [regex.search(kernelspec) for kernelspec in kernelspecs]
            has_match = [bool(match) for match in matches]
            if sum(has_match) == 1:
                kernel_full_name = kernelspecs[has_match.index(True)]
            else:
                raise ValueError("Can't find exactly one kernel matching '{0}' in list:\n{1}".format(kernel_name, kernelspecs))

        self._kernel_name = kernel_name
        self._kernel_full_name = kernel_full_name
        self._kernel_id = kernel_manager.start_kernel(kernel_full_name)
        self._kernel = kernel_manager.get_kernel(self._kernel_id)
        self._client = self._kernel.client()
        self._client.get_shell_msg(self._client.execute('import pickle, os'))

    def __repr__(self):
        return repr({k: self.__dict__[k] for k in self.__dict__ if not k.startswith('_')})

    def __del__(self):
        print('RemoteKernel: {0}.__del__'.format(self))
        self._shutdown()

    def _shutdown(self):
        self._kernel.shutdown_kernel()

    def _restart(self):
        if not self._kernel.is_alive():
            self._kernel.start_kernel()
        else:
            self._kernel.restart_kernel()
        self._client = self._kernel.client()
        self._client.get_shell_msg(self._client.execute('import pickle, os'))

    def _execute_code(self, code, directory, output_variables):
        import pickle
        pickle_dumps = 'pickle.dumps({' + ','.join(['"{0}":{0}'.format(variable) for variable in output_variables]) + '})'
        if not self._kernel.is_alive():
            self._restart()
        if directory:
            reply = self._client.get_shell_msg(self._client.execute('os.chdir("{0}")'.format(directory)))
            status = reply['content']['status']
            if status != 'ok':
                print('os.chdir("{0}") on {1} failed:\n\t{2}: {3}'.format(directory, self._kernel_name,
                                                                          reply['content']['ename'], reply['content']['evalue']))
        sent_msg_id = self._client.execute(code, user_expressions={'output':pickle_dumps})
        reply = self._client.get_shell_msg(sent_msg_id)
        status = reply['content']['status']
        if status != 'ok':
            print('Execution of code on {0} ({1}) failed:\n\t{2}: {3}'.format(self._kernel_name, self._kernel_full_name,
                                                                              reply['content']['ename'], reply['content']['evalue']))
        else:
            output_bytes = reply['content']['user_expressions']['output']['data']['text/plain']
            if not output_bytes.startswith('b'):
                output_bytes = bytes(output_bytes, 'utf-8')
            self.__dict__.update(pickle.loads(eval(output_bytes)))


# The class MUST call this class decorator at creation time
@magics_class
class RemoteKernelMagics(Magics):

    def __init__(self, **kwargs):
        # Create dictionary of server objects, each of which contains its
        # connection, a tuple of input variables, and a dictionary of output
        # variables.  The input and output variables should be addressable by a
        # dot.
        super(RemoteKernelMagics, self).__init__(**kwargs)
        from jupyter_client import MultiKernelManager
        from tempfile import gettempdir
        self.kernel_manager = MultiKernelManager()
        self.kernels = {}
        self.kernel_manager.connection_dir = gettempdir()

    def __del__(self):
        print('RemoteKernelMagics: {0}.__del__'.format(self))
        for key, value in self.kernels.items():
            value._shutdown()

    def close_kernels(self):
        print('RemoteKernelMagics: {0}.close_kernels()'.format(self))
        for key, value in self.kernels.items():
            print('\tClosing {0},{1}'.format(key,value))
            value._shutdown()

    @magic_arguments()
    @argument(
        '-k', '--kernels', required=True,
        help='Variables to be created in local scope, with names that match kernels on which to run the code'
    )
    @argument(
        '-o', '--output',
        help='Variables to be exported from the remote kernel into the local object representing that kernel'
    )
    @argument(
        '-i', '--input',
        help='Variables from local scope that will be substituted into the given code'
    )
    @argument(
        '-s', '--shutdown', action='store_true',
        help='Shut down the given kernels.  If code is also given with this option, the kernels will automatically restart before the code is run.'
    )
    @argument(
        'code',
        nargs='*',
    )
    @needs_local_scope
    @line_cell_magic
    def remote_exec(self, line, cell=None, local_ns=None):
        """Run code remotely via ipython kernels

        This command opens ipython kernels (possibly remotely with
        `remote_ikernel`) and runs the given code.  It then returns the
        requested output variables.

        Parameters
        ==========
        kernels: string, comma-separated list of strings, or variable containing such
            Name of kernels on which to run the code.  Each string must be a
            valid variable name, as it will be exported to the local namespace.
            The actual kernel names are searched for exact matches first of
            all, then for partial matches, and finally any underscore in these
            strings is used as a wild card to search for a match.  Any such
            match must occur exactly once.  Known kernels can be found from the
            command line with `jupyter-kernelspec list`.
        output: string or comma-separated list of strings
            Names of output variables to be returned.  Objects with the names
            of the servers above are injected into the local namespace, and
            these variables can be accessed within each of those objects.
        input: string or comma-separated list of strings
            Names of input variables to be used.  Each of these must be a
            dictionary in the local namespace, with keys given by the server
            names.  The corresponding values are then substituted into the code
            before it is run remotely wherever `{variable}` is found in the code.
        shutdown: bool, defaults to False
            Shut down the given kernels.  If code is also given along with this
            option, the kernels will automatically restart before the code is
            run.

        Exports
        =======
        kernel1,kernel2,...
            Objects named by the input `kernels`.  These contain the kernel
            connection, and the returned variables.  So, if the `output` option
            requests variables `x,y`, the result will be stored as `kernel1.x`,
            `kernel1.y`, `kernel2.x`, etc.  These appear in the local namespace
            in which this magic was used.

        """
        args = parse_argstring(self.remote_exec, line)

        # arguments 'code' in line are prepended to
        # the cell lines
        if cell is None:
            code = ''
            return_output = True
            line_mode = True
        else:
            code = cell
            return_output = False
            line_mode = False
        code = ' '.join(args.code) + '\n' + code

        # Look through the list of kernel names, and make sure they all exist and are connected
        if args.kernels.startswith('{') and args.kernels.endswith('}'):
            kernel_names = self.shell.user_ns[args.kernels[1:-1]].split(',')
        else:
            kernel_names = args.kernels.split(',')
        initial_directories = [None,]*len(kernel_names)
        for i, kernel_name in enumerate(kernel_names):
            if ':' in kernel_name:
                kernel_names[i], initial_directories[i] = kernel_name.split(':')
        for kernel_name in kernel_names:
            if not kernel_name in self.shell.user_ns:
                self.shell.user_ns[kernel_name] = RemoteKernel(self.kernel_manager, kernel_name)
            self.kernels[kernel_name] = self.shell.user_ns[kernel_name]

        # Make sure we have the local variables we claim to need
        if args.input:
            local_vars = args.input.split(',')
        else:
            local_vars = []
        for local_var in local_vars:
            if not local_var in self.shell.user_ns or not isinstance(self.shell.user_ns[local_var], dict):
                raise ValueError("No dictionary named '{0}' in local variables".format(local_var))
            for kernel_name in kernel_names:
                if not kernel_name in self.shell.user_ns[local_var]:
                    raise KeyError("No key '{0}' in dictionary '{1}'".format(kernel_name, local_var))

        # Make sure we have some list of output variables
        if args.output:
            output_variables = args.output.split(',')
        else:
            output_variables = []

        # Shutdown all listed kernels, if requested
        if args.shutdown:
            for kernel_name in kernel_names:
                self.shell.user_ns[kernel_name]._shutdown()

        # Now, step through and do the work
        if code:
            for kernel_name, initial_directory in zip(kernel_names, initial_directories):
                # Transform the code with the local variables
                custom_code = code
                for local_var in local_vars:
                    custom_code = custom_code.replace('{{{0}}}'.format(local_var),
                                                      self.shell.user_ns[local_var][kernel_name])

                self.shell.user_ns[kernel_name]._execute_code(custom_code, initial_directory, output_variables)


def close_kernels(ip):
    ip.magics_manager.registry['RemoteKernelMagics'].close_kernels()

    
def load_ipython_extension(ip):
    """Load the extension in IPython."""
    import atexit
    atexit.register(close_kernels, ip)
    ip.register_magics(RemoteKernelMagics)


def unload_ipython_extension(ip):
    """Unload the extension in IPython"""
    close_kernels(ip)

from IPython.core.magic import (Magics, magics_class, line_magic, cell_magic,
                                line_cell_magic, needs_local_scope)
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
            matches = [re_search.search(kernelspec) for kernelspec in kernelspecs]
            has_match = [bool(match) for match in matches]
            if sum(has_match) == 1:
                kernel_full_name = kernelspecs[has_match.index(True)]
            else:
                raise ValueError("Can't find exactly one kernel matching {0} in list:\n{1}".format(kernel_name, kernelspces))

        self._kernel_name = kernel_name
        self._kernel_full_name = kernel_full_name
        self._kernel_id = kernel_manager.start_kernel(kernel_full_name)
        self._kernel = kernel_manager.get_kernel(self._kernel_id)
        self._client = self._kernel.client()
        self._client.execute('import pickle, os')

    def __del__(self):
        self._client.shutdown_kernel()

    def _execute_code(self, code, directory, output_variables):
        import pickle
        pickle_dumps = 'pickle.dumps({' + ','.join(['"{0}":{0}'.format(variable) for variable in output_variables]) + '})'
        # if directory:
        #     self._client.execute('os.chdir({0})'.format(directory))
        # sent_msg_id = self._client.execute(code, user_expressions={'output':pickle_dumps})
        # reply = self._client.get_shell_msg(sent_msg_id)
        # self.__dict__.update(pickle.loads(eval(reply['content']['user_expressions']['output']['data']['text/plain'])))
        print("{0} is supposed to run this code:".format(self._kernel_name))
        print("-"*80)
        print(code)
        print("-"*80)
        print("in directory {0},".format(directory))
        print("with kernel {0},".format(self._kernel_full_name))
        print("and output {0}.".format(output_variables))
        print(pickle_dumps)
        print()


# The class MUST call this class decorator at creation time
@magics_class
class MyMagics(Magics):

    def __init__(self, **kwargs):
        # Create dictionary of server objects, each of which contains its
        # connection, a tuple of input variables, and a dictionary of output
        # variables.  The input and output variables should be addressable by a
        # dot.
        super(MyMagics, self).__init__(**kwargs)
        from jupyter_client import MultiKernelManager
        self.kernel_manager = MultiKernelManager()
        self.kernels = {}

    def __del__(self):
        for key, value in self.kernels:
            del value

    @magic_arguments()
    @argument(
        '-k', '--kernels', required=True,
        help=''
    )
    @argument(
        '-o', '--output',
        help=''
    )
    @argument(
        '-i', '--input',
        help='Variables from local scope that will be substituted into the given code'
    )
    @argument(
        'code',
        nargs='*',
    )
    @needs_local_scope
    @line_cell_magic
    def remote_exec(self, line, cell=None, local_ns=None):
        """Run code remotely via SSH

        This command logs in via SSH to remote servers, opens an ipython shell,
        and runs the given code.  It then returns the requested output
        variables.

        Parameters
        ==========
        s: string or comma-separated list of strings
            Name of server or servers on which to run the code.  These must be
            recognized by SSH, possibly via ~/.ssh/config.
        o: string or comma-separated list of strings
            Names of output variables to be returned.  Objects with the names
            of the servers above are injected into the local namespace, and
            these variables can be accessed within each of those objects.
        i: string or comma-separated list of strings
            Names of input variables to be used.  Each of these must be a
            dictionary in the local namespace, with keys given by the server
            names.  The corresponding values are then substituted into the code
            before it is run remotely.

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

        if args.output:
            output_variables = args.output.split(',')
        else:
            output_variables = []

        # Now, step through and do the work
        for kernel_name, initial_directory in zip(kernel_names, initial_directories):
            # Transform the code with the local variables
            custom_code = code
            for local_var in local_vars:
                custom_code = custom_code.replace('{{{0}}}'.format(local_var),
                                                  self.shell.user_ns[local_var][kernel_name])

            self.shell.user_ns[kernel_name]._execute_code(custom_code, initial_directory, output_variables)
            print()


# In order to actually use these magics, you must register them with a
# running IPython.  This code must be placed in a file that is loaded once
# IPython is up and running:
ip = get_ipython()
# You can register the class itself without instantiating it.  IPython will
# call the default constructor on it.
ip.register_magics(MyMagics)

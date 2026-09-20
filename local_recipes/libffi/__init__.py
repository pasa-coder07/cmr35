from pythonforandroid.recipe import Recipe
from pythonforandroid.util import current_directory
from os.path import join


class LibffiRecipe(Recipe):
    version = '3.4.6'
    url = 'https://github.com/libffi/libffi/releases/download/v{version}/libffi-{version}.tar.gz'
    name = 'libffi'
    built_libraries = {'libffi.so': '.libs'}
    patches = []

    def prebuild_arch(self, arch):
        # Release tarball has pre-generated configure - DO NOT run autoreconf
        pass

    def build_arch(self, arch):
        env = self.get_recipe_env(arch)
        build_dir = self.get_build_dir(arch.arch)
        install_dir = self.ctx.get_python_install_dir(arch.arch)
        with current_directory(build_dir):
            self.shprint(
                './configure',
                '--host=' + arch.command_prefix,
                '--prefix=' + install_dir,
                '--enable-static',
                '--disable-shared',
                _env=env)
            self.shprint('make', '-j' + str(self.ctx.num_make_jobs), _env=env)
            self.shprint('make', 'install', _env=env)

#!/usr/bin/env python
# -*- coding: utf-8 -*-

from conans import ConanFile, tools
import os
import json

class CrashpadConan(ConanFile):
    name = "crashpad"
    version = "20190528"
    description = "Crashpad is a crash-reporting system."
    author = "Rene Meusel <rene.meusel@nexenio.com>"
    license = "Apache-2.0"
    homepage = "https://chromium.googlesource.com/crashpad/crashpad"
    url = "https://github.com/bincrafters/conan-crashpad"
    topics = ("conan", "crash-reporting", "logging", "minidump", "crash")
    settings = "os", "compiler", "build_type", "arch"
    exports = [ "patches/*", "LICENSE.md" ]
    short_paths = True

    _commit_id = "ee1d5124a2bfec578a1474b048cf934d92dcf7ba"
    _source_dir = "crashpad"
    _build_name = "out/Conan"
    _build_dir = os.path.join(_source_dir, _build_name)

    def _depot_tools(self):
        return os.path.join(self.source_folder, "depot_tools")

    def _crashpad_source_base(self):
        return os.path.join(self.source_folder, "crashpad_source")

    def _crashpad_source(self):
        return os.path.join(self._crashpad_source_base(), "crashpad")

    def build_requirements(self):
        self.build_requires("depot_tools_installer/20190909@bincrafters/stable")
        self.build_requires("ninja_installer/1.9.0@bincrafters/stable")

    def _mangle_spec_for_gclient(self, solutions):
        return json.dumps(solutions)          \
                   .replace("\"", "\\\"")     \
                   .replace("false", "False") \
                   .replace("true", "True")

    def _make_spec(self):
        solutions = [{
            "url": "%s@%s" % (self.homepage, self.commit_id),
            "managed": False,
            "name": "%s" % (self.name),
        }]
        return "solutions=%s" % self._mangle_spec_for_gclient(solutions)

    def configure(self):
        # It's not a C project, but libcxx is hardcoded in the project
        del self.settings.compiler.libcxx

    def source(self):
        self.run("gclient config --spec=\"%s\"" % self._make_spec(), run_environment=True)
        self.run("gclient sync --no-history", run_environment=True)
        tools.patch(base_path=os.path.join(self._source_dir, "third_party/mini_chromium/mini_chromium"),
                    patch_file="patches/dynamic_crt.patch")

    def _setup_args_gn(self):
        args = ["is_debug=%s" % ("true" if self.settings.build_type == "Debug" else "false")]

        if self.settings.os == "Macos" and self.settings.get_safe("os.version"):
            args += [ "mac_deployment_target=\\\"%s\\\"" % self.settings.os.version ]
        if self.settings.os == "Windows" and self.settings.get_safe("compiler.runtime"):
            crt = str(self.settings.compiler.runtime)
            args += [ "dynamic_crt=%s" % ("true" if crt.startswith("MD") else "false") ]
        return " ".join(args)

    def build(self):
        with tools.chdir(self._source_dir):
            self.run('gn gen %s --args="%s"' % (self._build_name, self._setup_args_gn()), run_environment=True)
            self.run("ninja -j%d -C %s" % (tools.cpu_count(), self._build_name), run_environment=True)

    def _copy_lib(self, src_dir):
        self.copy("*.a", dst="lib",
                  src=os.path.join(self._build_dir, src_dir), keep_path=False)
        self.copy("*.lib", dst="lib",
                  src=os.path.join(self._build_dir, src_dir), keep_path=False)

    def _copy_headers(self, dst_dir, src_dir):
        self.copy("*.h", dst=os.path.join("include", dst_dir),
                         src=os.path.join(self._source_dir, src_dir))

    def _copy_bin(self, src_bin):
        self.copy(src_bin, src=self._build_dir, dst="bin")
        self.copy("%s.exe" % src_bin, src=self._build_dir, dst="bin")

    def package(self):
        self.copy("LICENSE", dst="licenses", src=self._source_dir,
                             ignore_case=True, keep_path=False)

        self._copy_headers("crashpad/client", "client")
        self._copy_headers("crashpad/util",   "util")
        self._copy_headers("mini_chromium",   "third_party/mini_chromium/mini_chromium")
        self._copy_lib("obj/client")
        self._copy_lib("obj/util")
        self._copy_lib("obj/third_party/mini_chromium")
        self._copy_bin("crashpad_handler")

    def package_info(self):
        self.cpp_info.includedirs = [ "include/crashpad", "include/mini_chromium" ]
        self.cpp_info.libdirs = [ "lib" ]
        self.cpp_info.libs = tools.collect_libs(self)

        if self.settings.os == "Macos":
            self.cpp_info.exelinkflags.append("-framework CoreFoundation")
            self.cpp_info.exelinkflags.append("-framework CoreGraphics")
            self.cpp_info.exelinkflags.append("-framework CoreText")
            self.cpp_info.exelinkflags.append("-framework Security")
            self.cpp_info.exelinkflags.append("-framework IOKit")
            self.cpp_info.exelinkflags.append("-lbsm")
            self.cpp_info.sharedlinkflags = self.cpp_info.exelinkflags

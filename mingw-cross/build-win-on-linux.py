#!/usr/bin/env python

# script to build windows installer packages for LAMMPS
# (c) 2017 Axel Kohlmeyer <akohlmey@gmail.com>

from __future__ import print_function
import sys,os,shutil,glob,re,subprocess,tarfile,gzip
try: from urllib.request import urlretrieve as geturl
except: from urllib import urlretrieve as geturl

try:
  import multiprocessing
  numcpus = multiprocessing.cpu_count()
except:
  numcpus = 1

# thirdparty library versions

eigenver = '3.3.4'
vorover = '0.4.6'

# helper functions

def error(str=None):
    if not str: print(helpmsg)
    else: print(sys.argv[0],"ERROR:",str)
    sys.exit()

def system(cmd):
    try:
        txt = subprocess.check_output(cmd,stderr=subprocess.STDOUT,shell=True)
    except subprocess.CalledProcessError as e:
        print("Command '%s' returned non-zero exit status" % e.cmd)
        error(e.output.decode('UTF-8'))
    return txt.decode('UTF-8')

def getsrctar(url):
    tmp = 'tmp.tar.gz'
    geturl(url,tmp)
    tar = tarfile.open(tmp)
    tar.extractall()
    tar.close()
    os.remove(tmp)

def getexe(url,name):
    gzname = name + ".gz"
    geturl(url,gzname)
    with gzip.open(gzname,'rb') as gz_in:
      with open(name,'wb') as f_out:
        shutil.copyfileobj(gz_in,f_out)
    gz_in.close()
    f_out.close()
    os.remove(gzname)

def patch(name):
    patchfile = "%s/patches/%s.patch" % (homedir,name)
    if os.path.exists(patchfile):
        print("Patching:",name,system("patch -p0 < %s" % patchfile))

def fullpath(path):
    return os.path.abspath(os.path.expanduser(path))

def which(program):
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None

# record location and name of python script
homedir, exename = os.path.split(fullpath(sys.argv[0]))

# default settings help message and default settings

bitflag = '64'
parflag = 'no'
thrflag = 'no'
revflag = 'stable'
verbose = False

helpmsg = """
Usage: python %s -b <bits> -j <cpus> -p <mpi> -t <thread> -r <rev> -v <yes|no>

Flags (all flags are optional, defaults listed below):
  -b : select Windows variant (default value: %s)
    -b 32       : build for 32-bit Windows
    -b 64       : build for 64-bit Windows
  -j : set number of CPUs for parallel make (default value: %d)
    -j <num>    : set to any reasonable number or 1 for serial make
  -p : select message passing parallel build (default value: %s)
    -p mpi      : build an MPI parallel version with MPICH2 v1.4.1p1
    -p no       : build a serial version using MPI STUBS library
  -t : select thread support (default value: %s)
    -t omp      : build with threads via OpenMP enabled
    -t no       : build with thread support disabled
  -r : select LAMMPS source revision to build (default value: %s)
    -r stable   : download and build the latest stable LAMMPS version
    -r unstable : download and build the latest patch release LAMMPS version
    -r master   : download and build the latest development snapshot
    -r patch_<date> : download and build a specific patch release
    -r <sha256> : download and build a specific snapshot version
  -v : select output verbosity
    -v yes      : print progress messages and output of make commands
    -v no       : print only progress messages

Example:
  python %s -r unstable -t omp -p mpi
""" % (exename,bitflag,numcpus,parflag,thrflag,revflag,exename)


# parse arguments

argv = sys.argv
argc = len(argv)
i = 1

while i < argc:
    if i+1 >= argc:
        print("\nMissing argument to flag:",argv[i])
        error()
    if argv[i] == '-b':
        bitflag = argv[i+1]
    elif argv[i] == '-j':
        numcpus = int(argv[i+1])
    elif argv[i] == '-p':
        parflag = argv[i+1]
    elif argv[i] == '-t':
        thrflag = argv[i+1]
    elif argv[i] == '-r':
        revflag = argv[i+1]
    elif argv[i] == '-v':
        if argv[i+1] in ['yes','Yes','Y','y','on','1','True','true']:
            verbose = True
        elif argv[i+1] in ['no','No','N','n','off','0','False','false']:
            verbose = False
        else:
            error("\nUnknown verbose keyword:",argv[i+1])
    else:
        print("\nUnknown flag:",argv[i])
        error()
    i+=2

# checks
if bitflag != '32' and bitflag != '64':
    error("Unsupported bitness flag %s" % bitflag)
if parflag != 'no' and parflag != 'mpi':
    error("Unsupported parallel flag %s" % parflag)
if thrflag != 'no' and thrflag != 'omp':
    error("Unsupported threading flag %s" % thrflag)
# test for valid revision name format: branch names, release tags, or commit hashes
rev1 = re.compile("^(stable|unstable|master)$")
rev2 = re.compile(r"^(patch|stable)_\d+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\d{4}$")
rev3 = re.compile(r"^[a-f0-9]{40}$")
if not rev1.match(revflag) and not rev2.match(revflag) and not rev3.match(revflag):
    error("Unsupported revision flag %s" % revflag)

# create working directory
builddir = "%s/tmp-%s-%s-%s-%s" % (fullpath('.'),bitflag,parflag,thrflag,revflag)
shutil.rmtree(builddir,True)
try:
    os.mkdir(builddir)
except:
    error("Cannot create temporary build folder: %s" % builddir)

# check for prerequisites and set up build environment
if bitflag == '32':
    cc_cmd = which('i686-w64-mingw32-gcc')
    cxx_cmd = which('i686-w64-mingw32-g++')
    fc_cmd = which('i686-w64-mingw32-gfortran')
    ar_cmd = which('i686-w64-mingw32-ar')
    size_cmd = which('i686-w64-mingw32-size')
    nsis_cmd = which('makensis')
    lmp_size = '-DLAMMPS_SMALLSMALL'
else:
    cc_cmd = which('x86_64-w64-mingw32-gcc')
    cxx_cmd = which('x86_64-w64-mingw32-g++')
    fc_cmd = which('x86_64-w64-mingw32-gfortran')
    ar_cmd = which('x86_64-w64-mingw32-ar')
    size_cmd = which('x86_64-w64-mingw32-size')
    nsis_cmd = which('makensis')
    lmp_size = '-DLAMMPS_SMALLBIG'

if parflag == 'mpi':
    mpi_inc = '-I%s/mpich2-win%s/include' % (builddir,bitflag)
else:
    mpi_inc = '-I../../src/STUBS'

print("""
Settings: building LAMMPS revision %s for %s-bit Windows
Message passing  : %s
Multi-threading  : %s
Home folder      : %s
Build folder     : %s
C compiler       : %s
C++ compiler     : %s
Fortran compiler : %s
Library archiver : %s
""" % (revflag,bitflag,parflag,thrflag,homedir,builddir,cc_cmd,cxx_cmd,fc_cmd,ar_cmd))

# switch to build folder
os.chdir(builddir)

# download and unpack some stuff
print("Downloading sources and tools")
url='http://download.lammps.org/thirdparty'
print("FFMpeg")
getexe("%s/ffmpeg-win%s.exe.gz" % (url,bitflag),"ffmpeg.exe")
print("gzip")
getexe("%s/gzip.exe.gz" % url,"gzip.exe")
print("MPICH2")
getsrctar("%s/mpich2-win%s-devel.tar.gz" % (url,bitflag))
print("OpenCL")
getsrctar("%s/opencl-win-devel.tar.gz" % url)
print("Eigen3")
getsrctar("%s/eigen-%s.tar.gz" % (url,eigenver))
eigendir = fullpath(glob.glob('eigen-*')[0])
print("Voro++")
getsrctar("%s/voro++-%s.tar.gz" % (url,vorover))
vorodir = fullpath(glob.glob('voro++*')[0])
print("LAMMPS")
getsrctar("https://github.com/lammps/lammps/archive/%s.tar.gz" % revflag)
lammpsdir = fullpath("lammps-%s" % revflag)

print("Building Voro++ in",vorodir)
os.chdir(vorodir)
patch('voro++')
system("make -j %d -C src CXX=%s CFLAGS='-O3' AR=%s voro++" \
       % (numcpus,cxx_cmd,ar_cmd))
shutil.move('src/voro++',"%s/voro++.exe" % builddir)
os.chdir(builddir)

print("Configuring and building LAMMPS libraries")

if parflag == 'no':
  print("MPI STUBS")
  os.chdir(lammpsdir+"/src/STUBS")
  system("make CC=%s CCFLAGS='-O2 -I.' ARCHIVE=%s " % (cc_cmd,ar_cmd))

print("AtC")
os.chdir(lammpsdir+"/lib/atc")
makecmd = "make -j %d CC=%s ARCHIVE=%s CCFLAGS=-O3 " % (numcpus,cxx_cmd,ar_cmd)
if parflag == 'mpi':
    txt = system(makecmd + "-f Makefile.mpi " \
                 + "CPPFLAGS='-I../../src -I../../../mpich2-win%s/include %s' " \
                 % (bitflag,lmp_size))
elif parflag == 'no':
    txt = system(makecmd + "-f Makefile.serial " \
                 + "CPPFLAGS='-I../../src -I../../src/STUBS %s' " % lmp_size)
if verbose: print(txt)
    
print("Awpmd")
os.chdir(lammpsdir+"/lib/awpmd")
makecmd = "make CC=%s ARCHIVE=%s " % (cxx_cmd,ar_cmd)
if parflag == 'mpi':
    txt = system(makecmd + "CCFLAGS='-O3 -Isystems/interact/TCP/ " \
                 + "-Isystems/interact -Iivutils/include " \
                 + "-DMPICH_IGNORE_CXX_SEEK " \
                 + "-I../../../mpich2-win%s/include -O3 ' -f Makefile.mpi" % bitflag)
elif parflag == 'no':
    txt = system(makecmd + "CCFLAGS='-O3 -Isystems/interact/TCP/ " \
                 + "-Isystems/interact -Iivutils/include " \
                 + "-I../../src/STUBS -O3 ' -f Makefile.mpi")
if verbose: print(txt)
    
print("Colvars")
os.chdir(lammpsdir+"/lib/colvars")
txt = system("make -j %d CXX=%s CXXFLAGS=-O3 AR=%s -f Makefile.serial" \
             % (numcpus,cxx_cmd,ar_cmd))
if verbose: print(txt)

# nothing to do for "Compress"

print("GPU")
os.chdir(lammpsdir+"/lib/gpu")
makecmd = "make AR=%s LMP_INC=%s -f Makefile.linux_opencl " % (ar_cmd,lmp_size) \
          + "OCL_TUNE=-DKEPLER_OCL OCL_PREC=-D_SINGLE_DOUBLE " \
          + "OCL_INC='-I../../../OpenCL/include' "

if parflag == 'mpi':
    makecmd += "OCL_LINK='-Wl,--enable-stdcall-fixup ../../../OpenCL/lib_win%s/libOpenCL.dll " % bitflag \
                + "-L../../../mpich2-win%s/lib -lmpi' " % bitflag \
                + "OCL_CPP='%s -O3 -DMPI_GERYON -DUCL_NO_EXIT " % cxx_cmd \
                + "-I../../../mpich2-win%s/include $(LMP_INC) $(OCL_INC) " % bitflag \
                + "-DMPICH_IGNORE_CXX_SEEK' "
    txt = system(makecmd + "ocl_get_devices")
    if verbose: print(txt)
    txt = system(makecmd + "-j %d" % numcpus)
elif parflag == 'no':
    makecmd += "OCL_LINK='-Wl,--enable-stdcall-fixup ../../../OpenCL/lib_win%s/libOpenCL.dll " % bitflag \
                + "-L../../src/STUBS -lmpi_stubs' " \
                + "OCL_CPP='%s -O3 -DMPI_GERYON -DUCL_NO_EXIT " % cxx_cmd \
                + "-I../../src/STUBS $(LMP_INC) $(OCL_INC)' "
    txt = system(makecmd + "ocl_get_devices")
    if verbose: print(txt)
    txt = system(makecmd + "-j %d" % numcpus)
if verbose: print(txt)
shutil.move('ocl_get_devices',"%s/ocl_get_devices.exe" % builddir)

# skipping h5md, kim, kokkos

print("LinAlg")
os.chdir(lammpsdir+"/lib/linalg")
txt = system("make -j %d FC=%s FFLAGS='-O3 -ffast-math -fstrict-aliasing' FFLAGS0='-O0' ARCHIVE=%s -f Makefile.serial" % (numcpus,fc_cmd,ar_cmd))
if verbose: print(txt)

print("MEAM")
os.chdir(lammpsdir+"/lib/meam")
txt = system("make -j %d F90=%s CC=%s ARCHIVE=%s -f Makefile.serial F90FLAGS='-O3 -ffast-math -fexpensive-optimizations' " % (numcpus,fc_cmd,cc_cmd,ar_cmd))
if verbose: print(txt)

# nothing to do for molfile
# skipping mscg, netcdf

print("POEMS")
os.chdir(lammpsdir+"/lib/poems")
txt = system("make -j %d CC=%s CCFLAGS=-O3 ARCHIVE=%s -f Makefile.serial" \
             % (numcpus,cxx_cmd,ar_cmd))
if verbose: print(txt)

# skipping python, qmmm, quip, reax

print("SMD")
os.chdir(lammpsdir+"/lib/smd")
os.symlink(eigendir,"includelink")

print("Voronoi")
os.chdir(lammpsdir+"/lib/voronoi")
os.symlink(vorodir+"/src","includelink")
os.symlink(vorodir+"/src","liblink")

print("Done")

print("Configuring and building LAMMPS itself")

os.chdir(lammpsdir+"/src")
system("make yes-all no-kokkos no-kim no-reax no-user-qmmm no-user-lb no-mpiio no-mscg no-user-netcdf no-user-intel no-user-quip no-python no-user-h5md no-user-vtk")
if parflag == "mpi": system("make yes-mpiio yes-user-lb")

makecmd = "make -j %d ARCHIVE=%s SHFLAG='' LINK='$(CC) -static' SIZE=echo " % (numcpus,ar_cmd)
if thrflag == 'omp':
    makecmd += "CC='%s -fopenmp' " % cxx_cmd
else:
    makecmd += "CC='%s' " % cxx_cmd

if bitflag == '32':
    makecmd += "CCFLAGS='-O3 -march=i686 -mtune=generic -mfpmath=387 -mpc64' "
elif bitflag == '64':
    makecmd += "CCFLAGS='-O3 -march=core2 -mtune=core2 -msse2 -mpc64 -ffast-math' "

makecmd += "LIB='-lwsock32 -static-libgcc -lquadmath -lpsapi' "
makecmd += "LMP_INC='%s -DLAMMPS_JPEG -DLAMMPS_PNG -DLAMMPS_XDR -DLAMMPS_GZIP -DLAMMPS_FFMPEG' " % lmp_size

makecmd += "JPG_LIB='-ljpeg -lpng -lz' molfile_SYSLIB='' "
makecmd += "gpu_SYSLIB='-Wl,--enable-stdcall-fixup ../../../OpenCL/lib_win%s/libOpenCL.dll' " % bitflag    

if parflag == 'mpi':
    makecmd += "MPI_INC='-I../../../mpich2-win%s/include -DMPICH_SKIP_MPICXX' " % bitflag
    makecmd += "MPI_PATH='-L../../../mpich2-win%s/lib' " % bitflag
    makecmd += "MPI_LIB='-lmpi' "
    txt = system(makecmd + "mpi")
    shutil.move('lmp_mpi',"%s/lmp_mpi.exe" % builddir)

elif parflag == 'no':
    makecmd += "MPI_INC='-I../STUBS' MPI_PATH='-L../STUBS' MPI_LIB='-lmpi_stubs' "
    txt = system(makecmd + "serial")
    shutil.move('lmp_serial',"%s/lmp_serial.exe" % builddir)
if verbose: print(txt)

print("Done")

error("xxx")
# clean up after successful build
os.chdir(homepath)
print("Cleaning up...")
shutil.rmtree(builddir,True)
print("Done.")
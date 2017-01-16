INCLUDE(FindPkgConfig)
PKG_CHECK_MODULES(PC_LLSR llsr)

FIND_PATH(
    LLSR_INCLUDE_DIRS
    NAMES llsr/api.h
    HINTS $ENV{LLSR_DIR}/include
        ${PC_LLSR_INCLUDEDIR}
    PATHS ${CMAKE_INSTALL_PREFIX}/include
          /usr/local/include
          /usr/include
)

FIND_LIBRARY(
    LLSR_LIBRARIES
    NAMES gnuradio-llsr
    HINTS $ENV{LLSR_DIR}/lib
        ${PC_LLSR_LIBDIR}
    PATHS ${CMAKE_INSTALL_PREFIX}/lib
          ${CMAKE_INSTALL_PREFIX}/lib64
          /usr/local/lib
          /usr/local/lib64
          /usr/lib
          /usr/lib64
)

INCLUDE(FindPackageHandleStandardArgs)
FIND_PACKAGE_HANDLE_STANDARD_ARGS(LLSR DEFAULT_MSG LLSR_LIBRARIES LLSR_INCLUDE_DIRS)
MARK_AS_ADVANCED(LLSR_LIBRARIES LLSR_INCLUDE_DIRS)


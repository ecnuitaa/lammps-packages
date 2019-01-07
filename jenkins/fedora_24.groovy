node {
    stage 'Checkout'
    git url: 'https://github.com/lammps/lammps.git', branch: 'master'

    dir('lammps-packages') {
        git url: 'https://github.com/lammps/lammps-packages.git', credentialsId: 'lammps-jenkins', branch: 'rpm-build'
    }

    def common = load 'lammps-packages/jenkins/common.groovy'

    def workdir = pwd()

    //env.CCACHE_DIR=workdir + '/.ccache'

    common.build_rpm('rbberger/lammps-testing:fedora_24')

    stage 'Archive RPMs'
    archiveArtifacts artifacts: 'rpmbuild/**/*.rpm', onlyIfSuccessful: true

    sh 'mkdir -p ${LAMMPS_DOWNLOAD_RPM_DIR}/fedora/24'
    sh 'find ${LAMMPS_DOWNLOAD_RPM_DIR}/fedora/24 -mtime +30 -exec rm {} \\;'
    sh 'cp -R rpmbuild/RPMS/x86_64 ${LAMMPS_DOWNLOAD_RPM_DIR}/fedora/24'

    step([$class: 'WarningsPublisher', canComputeNew: false, consoleParsers: [[parserName: 'GNU Make + GNU C Compiler (gcc)']], defaultEncoding: '', excludePattern: '', healthy: '', includePattern: '', messagesPattern: '', unHealthy: ''])
}
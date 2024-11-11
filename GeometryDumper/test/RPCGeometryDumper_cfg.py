import FWCore.ParameterSet.Config as cms

process = cms.Process("GeometryDumperProcess")

process.load('Configuration/StandardSequences/Services_cff')
process.load('FWCore/MessageService/MessageLogger_cfi')

######################################################################################################
### From autoCond at https://github.com/cms-sw/cmssw/blob/master/Configuration/AlCa/python/autoCond.py
######################################################################################################
#process.load("Configuration.StandardSequences.GeometryDB_cff")
#process.load('Configuration.StandardSequences.FrontierConditions_GlobalTag_cff')
#from Configuration.AlCa.autoCond import autoCond
#process.GlobalTag.globaltag = autoCond['run3_data']

######################################################################################################
### From specific global tag at https://cms-conddb.cern.ch/cmsDbBrowser/index/Prod
######################################################################################################
#process.load("Configuration.StandardSequences.GeometryDB_cff")
#process.load('Configuration.StandardSequences.FrontierConditions_GlobalTag_cff')
#from Configuration.AlCa.GlobalTag import GlobalTag
#process.GlobalTag = GlobalTag(process.GlobalTag, '140X_dataRun3_HLT_RPC_GEM_w13_2024_v1', '')


######################################################################################################
### From specific xml file at https://github.com/cms-sw/cmssw/tree/master/Configuration/Geometry/python
######################################################################################################
process.load('Configuration.Geometry.GeometryDD4hepExtended2024Reco_cff')

######################################################################################################
### The source data defines the time zone of the Geometry that the tag will load.
### Consider the payload of the tag (e.g. https://cms-conddb.cern.ch/cmsDbBrowser/list/Prod/tags/RecoIdealGeometry_RPC_v3_hlt)
######################################################################################################
process.source = cms.Source("PoolSource",
    #fileNames = cms.untracked.vstring('file:../data/root/sample.root') ## if you want to use local root file
    fileNames = cms.untracked.vstring('root://cms-xrd-global.cern.ch//store/data/Run2023D/Muon0/AOD/PromptReco-v1/000/370/580/00001/ed65f587-336e-4ca8-a4ed-14dd220c70dc.root')
)

process.maxEvents = cms.untracked.PSet( input = cms.untracked.int32(1) )

process.RPCGeometryDumper = cms.EDAnalyzer("RPCGeometryDumper",
    outputFileName = cms.untracked.string("rpc_geometry.csv"),
)

process.p = cms.Path(process.RPCGeometryDumper)

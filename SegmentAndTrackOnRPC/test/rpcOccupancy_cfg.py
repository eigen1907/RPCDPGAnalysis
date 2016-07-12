import FWCore.ParameterSet.Config as cms

process = cms.Process("RPCAnalysis")

process.load('Configuration/StandardSequences/Services_cff')
process.load('FWCore/MessageService/MessageLogger_cfi')
process.load("Configuration.StandardSequences.GeometryDB_cff")
#process.load("Configuration.Geometry.GeometryIdeal2015Reco_cff")
process.load('Configuration.StandardSequences.FrontierConditions_GlobalTag_condDBv2_cff')
from Configuration.AlCa.autoCond_condDBv2 import autoCond
#process.GlobalTag.globaltag = autoCond['run2_mc']
process.GlobalTag.globaltag = autoCond['run2_data']

process.maxEvents = cms.untracked.PSet( input = cms.untracked.int32(-1) )
process.options = cms.untracked.PSet(
    wantSummary = cms.untracked.bool(True),
    allowUnscheduled = cms.untracked.bool(True),
)
process.MessageLogger.cerr.FwkReport.reportEvery = 50000
process.source = cms.Source("PoolSource", fileNames = cms.untracked.vstring())

process.source.fileNames = [
#    '/store/mc/RunIIFall15DR76/DYJetsToLL_M-50_TuneCUETP8M1_13TeV-amcatnloFXFX-pythia8/AODSIM/PU25nsPoisson50_76X_mcRun2_asymptotic_v12_ext1-v1/20000/0069F61C-CBF3-E511-929C-02163E01769E.root'
    '/store/data/Run2016B/SingleMuon/RECO/PromptReco-v2/000/273/296/00000/0C50634A-441A-E611-B4FA-02163E0137E8.root',
]

process.goodVertices = cms.EDFilter("VertexSelector",
    src = cms.InputTag("offlinePrimaryVertices"),
    cut = cms.string("!isFake && ndof > 4 && abs(z) <= 24 && position.rho < 2"),
    filter = cms.bool(True),
)

process.rpcAn = cms.EDAnalyzer("RPCOccupancyAnalyzer",
    rpcRecHits = cms.InputTag("rpcRecHits"),
    #vertex = cms.InputTag("goodVertices"),
    muons = cms.InputTag("muons"),
)

process.TFileService = cms.Service("TFileService",
    fileName = cms.string("hist.root"),
)

process.p = cms.Path(process.rpcAn)

#process.out = cms.OutputModule("PoolOutputModule",
#    fileName = cms.untracked.string("a.root"),
#    outputCommands = cms.untracked.vstring("drop *", "keep *_*_*_RPCAnalysis"),
#)
#process.outPath = cms.EndPath(process.out)

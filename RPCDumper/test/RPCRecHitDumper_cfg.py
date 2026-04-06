import FWCore.ParameterSet.Config as cms

process = cms.Process("DUMP")

process.load('Configuration.Geometry.GeometryExtendedRun4D125Reco_cff')

process.source = cms.Source(
    "PoolSource",
    fileNames=cms.untracked.vstring("file:step3.root")
)
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(-1))

process.TFileService = cms.Service(
    "TFileService",
    fileName=cms.string("rechits.root")
)

process.rpcRecHitDumper = cms.EDAnalyzer(
    "RPCRecHitDumper",
    dumpRPCRecHit=cms.bool(True),
    rpcRecHitTag=cms.InputTag("rpcRecHits"),

    dumpRPCRecHitPhase2=cms.bool(True),
    rpcRecHitPhase2Tag=cms.InputTag("rpcRecHitsPhase2"),
)

process.p = cms.Path(process.rpcRecHitDumper)
import FWCore.ParameterSet.Config as cms
from FWCore.ParameterSet.VarParsing import VarParsing

options = VarParsing('analysis')
options.parseArguments()

process = cms.Process("DUMP")

process.load("Configuration.Geometry.GeometryExtendedRun4D125Reco_cff")
process.load("FWCore.MessageService.MessageLogger_cfi")
process.load("SimGeneral.TrackingAnalysis.simHitTPAssociation_cfi")

process.source = cms.Source(
    "PoolSource",
    fileNames=cms.untracked.vstring(
        options.inputFiles if options.inputFiles else "file:step3.root"
    )
)

process.maxEvents = cms.untracked.PSet(
    input=cms.untracked.int32(-1)
)

process.TFileService = cms.Service(
    "TFileService",
    fileName=cms.string(
        options.outputFile if options.outputFile else "rechits.root"
    )
)

process.simHitTPAssocProducer.simHitSrc = cms.VInputTag(
    cms.InputTag("g4SimHits", "MuonRPCHits")
)
process.simHitTPAssocProducer.trackingParticleSrc = cms.InputTag("mix", "MergedTrackTruth")

process.rpcRecHitDumper = cms.EDAnalyzer(
    "RPCRecHitDumper",
    dumpRPCRecHit=cms.bool(True),
    rpcRecHitTag=cms.InputTag("rpcRecHits"),

    dumpRPCRecHitPhase2=cms.bool(True),
    rpcRecHitPhase2Tag=cms.InputTag("rpcRecHitsPhase2"),

    simHitTag=cms.InputTag("g4SimHits", "MuonRPCHits"),
    trackingParticleTag=cms.InputTag("mix", "MergedTrackTruth"),
    simHitAssocTag=cms.InputTag("simHitTPAssocProducer"),
)

process.p = cms.Path(
    process.simHitTPAssocProducer +
    process.rpcRecHitDumper
)
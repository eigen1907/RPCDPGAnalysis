import FWCore.ParameterSet.Config as cms
from FWCore.ParameterSet.VarParsing import VarParsing

options = VarParsing('analysis')
options.parseArguments()

process = cms.Process("DUMP")

process.load('Configuration.Geometry.GeometryExtendedRun4D125Reco_cff')

process.source = cms.Source(
    "PoolSource",
    fileNames=cms.untracked.vstring(options.inputFiles if options.inputFiles else "file:step2.root")
)
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(-1))

process.TFileService = cms.Service(
    "TFileService",
    fileName=cms.string(options.outputFile if options.outputFile else "digis.root")
)

process.rpcDigiDumper = cms.EDAnalyzer(
    "RPCDigiDumper",
    dumpRPCDigi=cms.bool(True),
    rpcDigiTag=cms.InputTag("simMuonRPCDigis"),

    dumpIRPCDigi=cms.bool(True),
    irpcDigiTag=cms.InputTag("simMuonIRPCDigis"),

    dumpRPCDigiPhase2=cms.bool(True),
    rpcDigiPhase2Tag=cms.InputTag("simMuonRPCDigisPhase2"),
)

process.p = cms.Path(process.rpcDigiDumper)
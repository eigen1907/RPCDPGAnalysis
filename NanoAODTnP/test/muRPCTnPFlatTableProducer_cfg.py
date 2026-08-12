import FWCore.ParameterSet.Config as cms
from FWCore.ParameterSet.VarParsing import VarParsing
from Configuration.StandardSequences.Eras import eras
from Configuration.AlCa.GlobalTag import GlobalTag

options = VarParsing('analysis')
options.parseArguments()

process = cms.Process('RPCTnP', eras.Run3)
process.load('FWCore.MessageService.MessageLogger_cfi')
process.load('Configuration.StandardSequences.GeometryRecoDB_cff')
process.load('Configuration.StandardSequences.MagneticField_cff')
process.load('Configuration.StandardSequences.FrontierConditions_GlobalTag_cff')
process.load('DPGAnalysis.MuonTools.muRPCTnPFlatTableProducer_cfi')

process.maxEvents = cms.untracked.PSet(
    input = cms.untracked.int32(options.maxEvents)
)

from Configuration.AlCa.autoCond import autoCond
process.GlobalTag.globaltag = autoCond['run3_data']

process.source = cms.Source('PoolSource',
    fileNames = cms.untracked.vstring(options.inputFiles),
    secondaryFileNames = cms.untracked.vstring(),
    inputCommands=cms.untracked.vstring(
        'keep *',
        ### For 2022, 2023 Data
        'drop TotemFEDInfos_totemT2Digis_TotemT2_RECO',
        'drop TotemT2DigiedmNewDetSetVector_totemT2Digis_TotemT2_RECO',
        'drop TotemVFATStatusedmDetSetVector_totemT2Digis_TotemT2_RECO',
        ### For 2024 Data
        'drop floatBXVector_gtStage2Digis_CICADAScore_RECO',
    )
)

process.muRPCTnPFlatTableProducer.tagMuonTriggerMatchingPaths = [
    "HLT_IsoMu24",
    "HLT_IsoMu27",
    "HLT_IsoMu30",
    "HLT_Mu50",
    "HLT_Mu55"
]
process.rpcTnPPath = cms.Path(process.muRPCTnPFlatTableProducer)

process.load('PhysicsTools.NanoAOD.NanoAODEDMEventContent_cff')
outputCommands = process.NANOAODEventContent.outputCommands
outputCommands.extend([
    'keep nanoaodFlatTable_*_*_*',
    'drop edmTriggerResults_*_*_*',
])
process.out = cms.OutputModule('NanoAODOutputModule',
    fileName = cms.untracked.string(options.outputFile),
    outputCommands = outputCommands,
    SelectEvents = cms.untracked.PSet(
        SelectEvents=cms.vstring('rpcTnPPath')
    )
)

process.end = cms.EndPath(process.out)

process.schedule = cms.Schedule(
    process.rpcTnPPath,
    process.end
)

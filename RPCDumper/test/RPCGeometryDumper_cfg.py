import FWCore.ParameterSet.Config as cms

process = cms.Process("GeometryDumperProcess")

process.load('Configuration.Geometry.GeometryExtendedRun4D125Reco_cff')

process.source = cms.Source("EmptySource")
process.maxEvents = cms.untracked.PSet(
    input = cms.untracked.int32(1)
)

process.maxEvents = cms.untracked.PSet( input = cms.untracked.int32(1) )

process.RPCGeometryDumper = cms.EDAnalyzer("RPCGeometryDumper",
    outputFileName = cms.untracked.string("geometry.csv"),
)

process.p = cms.Path(process.RPCGeometryDumper)

#include "FWCore/Framework/interface/Frameworkfwd.h"
#include "FWCore/Framework/interface/one/EDAnalyzer.h"

#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/ParameterSet/interface/ParameterSetDescription.h"
#include "FWCore/ParameterSet/interface/ConfigurationDescriptions.h"

#include "FWCore/Utilities/interface/InputTag.h"
#include "FWCore/Framework/interface/Run.h"
#include "FWCore/Framework/interface/Event.h"
#include "DataFormats/Common/interface/Handle.h"

#include "FWCore/Framework/interface/ESHandle.h"
#include "Geometry/Records/interface/MuonGeometryRecord.h"
#include "Geometry/RPCGeometry/interface/RPCRollSpecs.h"
#include "Geometry/RPCGeometry/interface/RPCGeometry.h"
#include "Geometry/RPCGeometry/interface/RPCGeomServ.h"
#include "DataFormats/GeometrySurface/interface/TrapezoidalPlaneBounds.h"
#include "TrackingTools/GeomPropagators/interface/StraightLinePlaneCrossing.h"

#include "DataFormats/MuonDetId/interface/RPCDetId.h"

#include <iostream>
#include <fstream>

using namespace std;

class RPCGeometryDumper : public edm::one::EDAnalyzer<edm::one::WatchRuns>
{
public:
  explicit RPCGeometryDumper(const edm::ParameterSet&);
  ~RPCGeometryDumper() = default;

  static void fillDescriptions(edm::ConfigurationDescriptions&);

private:
  void beginRun(const edm::Run&, const edm::EventSetup&) override;
  void analyze(const edm::Event&, const edm::EventSetup&) override {};
  void endRun(const edm::Run&, const edm::EventSetup&) override {};

  edm::ESGetToken<RPCGeometry, MuonGeometryRecord> rpcGeomToken_;
  const std::string outputFileName_;

  const std::string header_ =
      "roll_name,region,ring,station,sector,layer,subsector,roll,rawId,area,"
      "x1,y1,z1,x2,y2,z2,x3,y3,z3,x4,y4,z4";
  const char delimiter_ = ',';
};

RPCGeometryDumper::RPCGeometryDumper(const edm::ParameterSet& iConfig)
    : rpcGeomToken_(esConsumes<edm::Transition::BeginRun>()),
      outputFileName_(iConfig.getUntrackedParameter<std::string>("outputFileName"))
{}

void RPCGeometryDumper::fillDescriptions(edm::ConfigurationDescriptions& descriptions)
{
  edm::ParameterSetDescription desc;
  desc.setUnknown();
  descriptions.addWithDefaultLabel(desc);
}

void RPCGeometryDumper::beginRun(const edm::Run&, const edm::EventSetup& iSetup)
{
  const auto& rpcGeom = iSetup.getData(rpcGeomToken_);

  std::ofstream fout(outputFileName_);
  fout << header_ << std::endl;

  for (const RPCRoll* roll : rpcGeom.rolls())
  {
    const RPCDetId detId = roll->id();
    const string roll_name = RPCGeomServ(detId).name();

    const int region    = detId.region();
    const int ring      = detId.ring();
    const int station   = detId.station();
    const int sector    = detId.sector();
    const int layer     = detId.layer();
    const int subsector = detId.subsector();
    const int roll_num   = detId.roll();

    const auto& bound = roll->surface().bounds();
    const float h = bound.length();
    const float w12 = bound.width();
    float w34;
    float area;

    if (roll->isBarrel())
    {
      w34 = w12;
      area = w12 * h;
    }
    else
    {
      w34 = 2 * bound.widthAtHalfLength() - w12;
      area = 2 * bound.widthAtHalfLength() * h;
    }

    const auto gp1 = roll->toGlobal(LocalPoint(-w12 / 2, +h / 2, 0.f));
    const auto gp2 = roll->toGlobal(LocalPoint(+w12 / 2, +h / 2, 0.f));
    const auto gp3 = roll->toGlobal(LocalPoint(+w34 / 2, -h / 2, 0.f));
    const auto gp4 = roll->toGlobal(LocalPoint(-w34 / 2, -h / 2, 0.f));

    fout << roll_name        << delimiter_
         << region          << delimiter_
         << ring            << delimiter_
         << station         << delimiter_
         << sector          << delimiter_
         << layer           << delimiter_
         << subsector       << delimiter_
         << roll_num        << delimiter_
         << detId.rawId()   << delimiter_
         << area            << delimiter_
         << gp1.x()         << delimiter_
         << gp1.y()         << delimiter_
         << gp1.z()         << delimiter_
         << gp2.x()         << delimiter_
         << gp2.y()         << delimiter_
         << gp2.z()         << delimiter_
         << gp3.x()         << delimiter_
         << gp3.y()         << delimiter_
         << gp3.z()         << delimiter_
         << gp4.x()         << delimiter_
         << gp4.y()         << delimiter_
         << gp4.z()         << std::endl;
  }
}

#include "FWCore/Framework/interface/MakerMacros.h"
DEFINE_FWK_MODULE(RPCGeometryDumper);
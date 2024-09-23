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
    
  const std::string header_ = "roll_name,det_id,area,is_front,x1,y1,z1,x2,y2,z2,x3,y3,z3,x4,y4,z4";
  const char delimeter_ = ',';
};

RPCGeometryDumper::RPCGeometryDumper(const edm::ParameterSet& iConfig):
  rpcGeomToken_(esConsumes<edm::Transition::BeginRun>()), 
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
  
  for ( const RPCRoll* roll : rpcGeom.rolls() )
  {
    const auto detId = roll->id();
    const string rollName = RPCGeomServ(detId).name();
    bool isFront = false;
    if (detId.ring() == 1 && detId.station()) 
    {
      isFront = (detId.subsector() != 2);
      if (detId.sector() % 2 == 0) isFront = !isFront;
    } 
    else 
    {
      isFront = (detId.subsector() % 2 == 0);
    }

    const auto& bound = roll->surface().bounds();
    const float h = bound.length();
    const float w12 = bound.width();
    float w34;
    float area;
    if ( roll->isBarrel() )
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

    fout << rollName        << delimeter_
         << detId.rawId()   << delimeter_
         << area            << delimeter_
         << isFront         << delimeter_
         << gp1.x()         << delimeter_
         << gp1.y()         << delimeter_
         << gp1.z()         << delimeter_
         << gp2.x()         << delimeter_
         << gp2.y()         << delimeter_
         << gp2.z()         << delimeter_
         << gp3.x()         << delimeter_
         << gp3.y()         << delimeter_
         << gp3.z()         << delimeter_
         << gp4.x()         << delimeter_
         << gp4.y()         << delimeter_
         << gp4.z()         << std::endl;
  }
}

#include "FWCore/Framework/interface/MakerMacros.h"
DEFINE_FWK_MODULE(RPCGeometryDumper);

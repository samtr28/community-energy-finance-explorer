import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
# This is a module.
# You can define variables and functions here, and use them from any form. For example, in a top-level form:
#
#    from ..resources import Module1
#
#    Module1.say_hello()
#
funding_resources = [
  {
    "title": "BC Community Climate Funding Guide",
    "description": "Find funding opportunities for your community climate action projects. This guide simplifies your search and connects you to programs that support sustainable, resilient communities across British Columbia. The guide includes a filter for funding programs related to clean energy.",
    "url": "https://communityclimatefunding.gov.bc.ca/",
    "notes": "",
  },
  {
    "title": "Green Municipal Fund – Community Energy Systems: Study",
    "description": "GMF funding support for business cases and feasibility studies to outline the design of a proposed community energy system.",
    "url": "https://greenmunicipalfund.ca/funding/study-community-energy-systems",
    "notes": "",
  },
  {
    "title": "Indigenous Loan Guarantee Program",
    "description": "Federal loan guarantee program supporting Indigenous equity ownership in energy and natural resource projects.",
    "url": "https://cilgc-cgpac.ca/en/program",
    "notes": "Canada-wide; useful for ownership and project finance models.",
  },
  {
    "title": "Alberta Indigenous Opportunities Corporation — Loan Guarantees",
    "description": "AIOC provides provincial loan guarantees that can help eligible Indigenous groups access financing for ownership stakes in major projects, including energy and other infrastructure-related opportunities.",
    "url": "https://theaioc.com/indigenous-groups/loan-guarantees/",
    "notes": "",
  },
  {
    "title": "Ontario Indigenous Opportunities Financing Program",
    "description": "Ontario loan guarantee program supporting Indigenous equity participation in eligible energy and resource development projects.",
    "url": "https://buildingonfund.ca/iofp/",
    "notes": "Expanded beyond energy, but energy is 1/3 core focus.",
  },
  {
    "title": "Saskatchewan Indigenous Investment Finance Corporation",
    "description": "Saskatchewan loan guarantee program supporting Indigenous equity ownership in major projects, including energy and related infrastructure.",
    "url": "https://siifc.ca/program/",
    "notes": "",
  },
  {
    "title": "Manitoba Indigenous Loan Guarantee Program",
    "description": "Manitoba's Indigenous Loan Guarantee Program provides provincial credit support to help eligible Indigenous Nations finance ownership stakes in major renewable energy and infrastructure projects.",
    "url": "https://www.gov.mb.ca/milgp/index.html",
    "notes": "",
  },
  {
    "title": "BC Indigenous Clean Energy Initiative",
    "description": "Funding program administered by New Relationship Trust (NRT) that supports BC First Nations in planning and implementing local clean energy projects, such as solar, hydro, wind, and energy efficiency upgrades.",
    "url": "https://newrelationshiptrust.ca/indigenous-clean-energy-initiative-bcicei/",
    "notes": "Focused on Indigenous communities.",
  },
  {
    "title": "Government of Canada Grants and Funding Finder",
    "description": "Federal portal that directs users to more specific grant and contribution funding finders using various filters.",
    "url": "https://www.canada.ca/en/government/grants-funding.html",
    "notes": "",
  },
  {
    "title": "Wah-ila-toos: Clean Energy in Indigenous, Rural and Remote Communities",
    "description": "Federal clean energy pathfinding and funding support for Indigenous, rural, and remote communities, including support across project stages from training and feasibility to clean energy implementation.",
    "url": "https://www.canada.ca/en/services/environment/weather/climatechange/climate-plan/reduce-emissions/reducing-reliance-diesel.html",
    "notes": "",
  },
  {
    "title": "Indigenous Climate Hub – Funding",
    "description": "Funding search page that lets users filter climate-related funding programs by distinction, program type, intake status, and topic.",
    "url": "https://indigenousclimatehub.ca/funding/",
    "notes": "Broader than energy but many relevant funding opportunities.",
  },
  {
    "title": "Tapestry Community Capital – Raise Capital",
    "description": "Tapestry supports qualified non-profits, charities, and co-operatives to raise community investment through community bonds.",
    "url": "https://tapestrycapital.ca/raise-capital/",
    "notes": "",
  },
  {
    "title": "GoParity Canada – Get Funded",
    "description": "GoParity Canada is a regulated impact investment platform where organizations can leverage crowdfunding to raise debt financing for climate and social projects.",
    "url": "https://goparity.ca/organizations/get-funded",
    "notes": "",
  },
  {
    "title": "Indigenous Energy Support Program (IESP) by IESO",
    "description": "Annual initiative funded by the Independent Electricity System Operator (IESO) to support First Nation and Métis communities in Ontario. It provides funding for energy planning, capacity building, and infrastructure development to foster community energy independence and clean energy projects.",
    "url": "https://www.ieso.ca/Get-Involved/Indigenous-Relations/Indigenous-Energy-Support-Program/Legacy-Energy-Support-Programs",
    "notes": "Ontario.",
  },
  {
    "title": "First Nations Clean Energy Business Fund",
    "description": "BC provincial program offering capacity and equity funding to First Nations to support feasibility studies, community energy planning, and taking equity positions in clean energy projects within their traditional territories.",
    "url": "https://www2.gov.bc.ca/gov/content/environment/natural-resource-stewardship/consulting-with-first-nations/first-nations-clean-energy-business-fund",
    "notes": "",
  },
  {
    "title": "Smart Renewables and Electrification Pathways Program – Indigenous-Led Clean Energy Stream (SREPs ILCE)",
    "description": "NRCan program providing funding for Indigenous communities and organizations to develop renewable energy and grid modernization projects, with a dedicated stream for Indigenous-led initiatives and a target of 50% Indigenous ownership across approved projects.",
    "url": "https://natural-resources.canada.ca/climate-change/sreps",
    "notes": "",
  },
  {
    "title": "Canada Infrastructure Bank – Indigenous Infrastructure",
    "description": "Federal Crown corporation offering loans and project acceleration funding to First Nation, Métis, and Inuit communities for clean energy infrastructure, including a dedicated Indigenous Equity Initiative to help communities purchase equity stakes in major projects.",
    "url": "https://cib-bic.ca/en/indigenous-infra/",
    "notes": "",
  },
]

educational_resources = [
  {
    "title": "Clean Electricity Project Equity Guide",
    "description": "Developed by Indigenous Clean Energy in collaboration with Clean Energy BC, this guide helps leadership understand how equity positions in major utility-scale clean electricity projects can secure greater economic and social benefits for Nations.",
    "url": "https://indigenouscleanenergy.com/wp-content/uploads/2025/12/ICE_clean-electricity-projects-equity-guide-digital.pdf",
    "notes": "",
  },
  {
    "title": "Canadian Community Finance Intermediaries",
    "description": "",
    "url": "https://opportunityfinancecan.netlify.app/",
    "notes": "",
  },
  {
    "title": "Regenerative Energy – National Survey 2026",
    "description": "The third annual survey report by Indigenous Clean Energy, presenting a national snapshot of how First Nations, Inuit, and Métis peoples and communities are shaping Canada's energy future through innovation, stewardship, and community-driven solutions.",
    "url": "https://indigenouscleanenergy.com/regenerative-energy-national-survey-2026/",
    "notes": "",
  },
  {
    "title": "The Case for Investing in Clean Energy in Remote Communities",
    "description": "This report summarizes key barriers facing renewable energy deployment in remote communities as they relate to accessing capital, and recommends government policies, programs, and tools to attract market capital and improve the business case for renewables in remote areas in Canada.",
    "url": "https://www.pembina.org/pub/case-investing-clean-energy-remote-communities",
    "notes": "",
  },
  {
    "title": "Empowering Communities, Energizing the Nation: Scaling Up Renewable Energy Cooperatives in Canada",
    "description": "Policy brief examining barriers and opportunities for scaling renewable energy co-operatives in Canada, including financing constraints, ownership structures, and policy recommendations to support community-owned clean energy.",
    "url": "https://www.schoolofpublicpolicy.sk.ca/research-ideas/publications-and-policy-insight/policy-brief/renewable-energy-cooperatives.php",
    "notes": "Canada-wide scope; useful for policy and finance framing of co-op energy enterprise models.",
  },
  {
    "title": "Employee Ownership Models",
    "description": "Different models for involving employees in financing a community energy enterprise. Some models have tax advantages.",
    "url": "https://www.employee-ownership.ca/types-of-employee-ownership/",
    "notes": "Contact Lorin Busaan if further info required.",
  },
]
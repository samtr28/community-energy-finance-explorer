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

factsheets = [
  {
    "title": "Community Bonds",
    "summary": "Community bonds are a debt financing instrument that helps organizations raise capital from community members and other investors to fund revenue generating projects.",
    "image": "_/theme/Factsheets/Community_Bonds_Infographic.png",  # path to your uploaded image
    "pdf_url": "https://impactinvestinghub.ca/wp-content/uploads/2026/05/FS-Community-Bonds-May-2026.pdf"
  },
  {  "title": "Loan Guarantees",
    "summary": "Loan guarantees are a risk-sharing tool that helps organizations secure loans for projects by improving lender confidence and borrowing terms.",
    "image": "_/theme/Factsheets/Loan_Guarantees_Infographic.png",  # path to your uploaded image
    "pdf_url": "https://impactinvestinghub.ca/wp-content/uploads/2026/05/FS-Loan-Guarantees-May-2026.pdf"
  },
  {  "title": "Crowdfunding",
     "summary": "Investment crowdfunding is a form of crowdfunding where people contribute money as investors, rather than as donors, to help finance a project or organization.",
     "image": "_/theme/Factsheets/Crowdfunding_Infographic.png",  # path to your uploaded image
     "pdf_url": "https://impactinvestinghub.ca/wp-content/uploads/2026/05/FS-Investment-Crowdfunding-May-2026.pdf"
  },

]
import pathlib as _pl; _R=_pl.Path(__file__).resolve().parent.parent/"data"
#!/usr/bin/env python3
"""Builds the ISB Exec Ed market taxonomy: 14 themes -> sub-themes -> topics.

Themes are the recurring TOP-LEVEL categories actually observed across the 11
captured school catalogues (see taxonomy_sources.md for the crosswalk), so
leadership recognises them. Topics carry an ai_era flag and keyword patterns so
programme classification is deterministic and re-runnable.
"""
import csv, os, re

# theme -> subtheme -> [(topic, ai_flag, keywords)]
# ai_flag: New (did not meaningfully exist pre-2023) | Transformed | Stable
T = {}

T["Leadership & Executive Capability"] = {
 "Foundational leadership": [
  ("Transition to leadership / first-time manager","Stable","first time manager;new manager;emerging leader;transition to leader;supervisory;frontline leader;transition to business leader"),
  ("Leading in the first 90 days / role transition","Stable","first 90 days;new role;role transition;stepping up;new in role"),
  ("Leading mid-level to senior transition","Stable","middle manager;mid-level;senior manager programme;general manager transition"),
  ("Authentic and purpose-driven leadership","Stable","authentic leader;purpose-driven;leadership identity;values-based lead"),
  ("Leadership styles and situational leadership","Stable","leadership style;situational leader;adaptive leader"),
 ],
 "Senior and C-suite leadership": [
  ("CEO / top management leadership","Stable","chief executive;ceo programme;top management;senior executive programme;senior executive leadership;senior leaders programme;senior leadership programme;senior leader programme"),
  ("Becoming a C-suite officer (role-specific ladders)","Stable","chief .* officer;cxo;c-suite;becoming an? (ceo|cfo|cio|cto|cmo|coo|chro|cxo|c-suite)"),
  ("Leading the enterprise / enterprise-wide leadership","Stable","enterprise leadership;leading the enterprise;enterprise-wide leader"),
  ("Executive transitions and succession","Stable","succession;executive transition;leadership pipeline"),
  ("Leading a P&L / business unit","Stable","p&l;business unit lead;profit centre"),
 ],
 "Leading people and teams": [
  ("Leading high-performing teams","Stable","high.performing team;team effectiveness;team dynamics;teaming"),
  ("Leading hybrid, remote and distributed teams","Transformed","hybrid team;remote team;distributed team;virtual team"),
  ("Coaching and the leader as coach","Stable","leader as coach;coaching skill;executive coaching;coaching for performance;leadership coaching;coaching"),
  ("Feedback and difficult conversations","Stable","difficult conversation;feedback skill;candid conversation"),
  ("Psychological safety and inclusive team culture","Stable","psychological safety;inclusive team;belonging"),
  ("Motivation, engagement and retention of talent","Stable","employee engagement;motivation;employee retention;talent retention;retention of talent"),
  ("Delegation and managing through others","Stable","delegation;managing through others;span of control"),
 ],
 "Leading human-AI organisations": [
  ("Leading teams that include AI agents","New","human.ai team;ai teammate;agent boss;human.agent team;teams of ai agents;managing ai agents;leading ai agents;teams? (in|with) (the )?ai;reinventing teams"),
  ("Redesigning managerial work around AI","New","managerial work;manager.s job;future of management;management practice.*ai;redesign.*manag"),
  ("Building AI fluency and adoption in the workforce","New","ai fluency;ai adoption;ai upskilling;ai enablement;ai.ready workforce;ai readiness"),
  ("Trust, accountability and human oversight of AI decisions","New","human oversight;human in the loop;ai trust;trust in ai"),
  ("Leading through AI-driven workforce disruption","New","workforce disruption;ai.*jobs?;reskilling at scale;ai transition"),
  ("Supervising and quality-assuring AI output","New","ai output;verify(ing)? ai;checking ai;ai quality;human review of ai;error correction"),
  ("Work redesign to convert AI time savings into output","New","work redesign;workflow redesign;reclaim time;time savings;capacity release"),
  ("Human-agent ratio and span-of-control design","New","human.agent ratio;agents? per (manager|human|employee);team design.*agent"),
 ],
 "Change, resilience and crisis": [
  ("Leading change and transformation","Stable","change management;leading change;change leadership;transformation leader"),
  ("Organisational resilience","Stable","organisational resilience;resilient organisation;business resilience"),
  ("Personal resilience, wellbeing and burnout","Stable","resilience;wellbeing;well-being;burnout;mindfulness;stress management;breathwork"),
  ("Crisis leadership and business continuity","Stable","crisis;business continuity;emergency;disaster"),
  ("Leading in uncertainty, volatility and ambiguity","Stable","uncertainty;volatil;ambiguity;turbulent;disruption leadership;turbulen;turbulan"),
  ("Turnaround and restructuring leadership","Stable","turnaround;restructuring;distressed;corporate failure;learning from failure"),
 ],
}

T["Strategy"] = {
 "Corporate and competitive strategy": [
  ("Competitive strategy and advantage","Stable","competitive strategy;competitive advantage;strategic management;strategy formulation"),
  ("Corporate strategy, portfolio and diversification","Stable","corporate strategy;portfolio strategy;diversification;parenting advantage"),
  ("Strategic thinking for executives","Stable","strategic thinking;strategic mindset;thinking strategically"),
  ("Growth strategy and scaling","Stable","growth strategy;scaling;scale up;scale-up;growth leadership"),
  ("Business model innovation and reinvention","Transformed","business model;value proposition design"),
  ("Platform and ecosystem strategy","Transformed","platform strategy;ecosystem;network effect;multi-sided"),
 ],
 "Strategy execution": [
  ("Strategy execution and implementation","Stable","strategy execution;executing strategy;implement.*strategy;from strategy to"),
  ("OKRs, balanced scorecard and performance management systems","Stable","okr;balanced scorecard;performance management system;kpi"),
  ("Strategic planning and budgeting cycles","Stable","strategic planning;annual plan;budgeting cycle"),
  ("Organisation design and operating models","Stable","organisation design;organizational design;operating model;org structure"),
  ("Strategic project and programme governance","Stable","programme governance;project portfolio;pmo"),
 ],
 "AI-era strategy": [
  ("AI strategy for the enterprise","New","ai strategy;ai roadmap;ai for leaders;ai for senior;ai for cxo;ai for business leaders;ai for executives;business of ai;ai transformation;ai at scale;ai.powered organi;ai.led transformation;enterprise ai;embracing ai;ai in (your|the) organi;winning with ai;competing in the age of ai"),
  ("Competing when AI collapses cost curves","New","ai disrupt;ai.*competitive;ai economics;cost curve"),
  ("Build-vs-buy and AI vendor/partner strategy","New","build.*buy;ai vendor;ai partner;model selection"),
  ("Data strategy as competitive strategy","Transformed","data strategy;data as asset;data monetis;data monetiz"),
  ("AI-native business models","New","ai.native;ai.first;ai business model"),
 ],
 "Geopolitics and macro strategy": [
  ("Geopolitics for business leaders and boards","New","geopolitic;geo-politic;statecraft;corporate diplomacy"),
  ("Trade, tariffs and supply-chain geopolitics","Transformed","tariff;trade war;trade policy;friendshoring;nearshoring;reshoring"),
  ("Macroeconomics for executives","Stable","macroeconomic;economics for manager;economic environment"),
  ("Country and emerging-market strategy","Stable","emerging market;country strategy;india strategy;doing business in"),
  ("Regulatory and political risk","Transformed","political risk;regulatory risk;nonmarket strateg;non-market strateg"),
 ],
 "M&A and corporate development": [
  ("M&A strategy and deal rationale","Stable","mergers;acquisition;m&a;m and a"),
  ("Valuation and deal structuring","Stable","deal valuation;deal structur;due diligence"),
  ("Post-merger integration","Stable","post.merger;post merger;integration planning;pmi"),
  ("Divestitures, carve-outs and restructuring","Stable","divestiture;carve.out;spin.off"),
  ("Alliances, joint ventures and partnerships","Stable","alliance;joint venture;strategic partnership"),
 ],
}

T["AI, Data & Digital"] = {
 "AI foundations for leaders": [
  ("AI and machine learning fundamentals for executives","Transformed","ai fundamental;machine learning;ai for business;ai for managers?;ai essentials;applied ai;ai and analytics;ai & analytics;deep learning;neural network;ai and ml;ai & ml;ai/ml;aiml;ai and machine learning;ai ml"),
  ("Generative AI foundations and prompting","New","generative ai;gen ai;genai;gen-ai;prompt;llms?;large language model;chatgpt;copilot"),
  ("Agentic AI and autonomous workflows","New","agentic;ai agents?;autonomous agents?;multi.agent;agent(ic)? systems?;agent workflow"),
  ("Data and AI literacy for non-technical leaders","Transformed","data literacy;ai literacy;non-technical;demystif"),
  ("Evaluating AI use cases and ROI","New","ai use case;ai roi;ai value;ai business case;ai prioriti"),
 ],
 "AI governance, risk and regulation": [
  ("AI governance frameworks and operating models","New","ai governance;responsible ai;ai oversight;ai policy;governing ai"),
  ("AI risk, safety and model assurance","New","ai risk;ai safety;ai assurance;model risk;ai audit;explainable ai;xai"),
  ("AI regulation and compliance (EU AI Act, DPDP, sectoral)","New","ai act;ai regulation;ai compliance;dpdp;data protection law"),
  ("AI ethics, bias and fairness","New","ai ethic;ethical ai;algorithmic bias;ai bias;bias in ai;ai fairness;fairness in ai;accountable ai"),
  ("Board oversight of AI","New","board.*ai;ai for boards?;ai for directors?"),
  ("Board and ExCo AI literacy as regulatory evidence","New","ai literacy obligation;article 4;evidenc.*literacy;regulator.*literacy"),
  ("Model observability and assurance for leaders","New","observability;model monitoring;model drift;data drift;ai assurance for leader"),
 ],
 "Digital transformation": [
  ("Enterprise digital transformation strategy and roadmaps","Transformed","digital transformation;digital strategy;digitis;digitiz;digital business"),
  ("Legacy modernisation, cloud and platform migration","Stable","cloud;legacy modernis;modernization;saas;enterprise architecture;it architecture;technology architecture"),
  ("Digital operating model, agile at scale and product operating model","Transformed","agile at scale;product operating model;digital operating model;devops;scaled agile"),
  ("Digital customer experience and omnichannel","Transformed","customer experience;cx;omnichannel;digital customer"),
  ("Automation, RPA and process digitisation","Transformed","automation;rpa;process digit;intelligent automation"),
 ],
 "Data, analytics and decisions": [
  ("Business analytics for decision-making","Stable","business analytic;analytics for;data driven decision;data-driven decision;business intelligence;data to decision;decision analytic;applied analytic;advanced analytic;big data"),
  ("Data science and applied statistics for managers","Stable","data science;statistic;predictive model;machine learning applied;predictive analytic;quantitative method;econometric;resource optimisation;optimisation model;operations research"),
  ("Data visualisation and storytelling with data","Stable","visualis;visualiz;storytelling (with|through|using) data;data storytelling;dashboard"),
  ("Data governance, quality and architecture","Transformed","data governance;data quality;data architecture;data management"),
  ("Experimentation, causal inference and A/B testing","Stable","experiment;a/b test;causal;randomised;randomized"),
  ("AI-augmented decision-making and judgment","New","ai.powered decision;ai.driven decision;ai.{0,15}decision;decision.*ai;augmented decision;algorithmic decision;intelligent decision"),
 ],
 "Cybersecurity and technology risk": [
  ("Cybersecurity strategy for leaders and boards","Transformed","cyber;information security;infosec"),
  ("Data privacy and protection","Transformed","privacy;data protection;gdpr;dpdp"),
  ("Technology and operational resilience risk","Transformed","technology risk;operational resilience;it risk;third party risk"),
 ],
 "Emerging technology": [
  ("Blockchain, tokenisation and Web3","Stable","blockchain;web3;tokenis;tokeniz;crypto;distributed ledger"),
  ("IoT, digital twins and Industry 4.0","Stable","internet of things;iot;digital twin;industry 4"),
  ("Quantum, robotics and frontier technology","Stable","quantum;robotic;frontier tech;deep tech"),
  ("Immersive technology, AR/VR and spatial computing","Stable","augmented reality;virtual reality;metaverse;spatial comput"),
 ],
}

T["Finance & Accounting"] = {
 "Finance for executives": [
  ("Finance for non-finance managers","Stable","finance for non.finance;finance for manager;financial acumen;financial literacy"),
  ("Financial statement analysis and accounting for decisions","Stable","financial statement;accounting;financial reporting;ifrs"),
  ("Corporate finance and capital allocation","Stable","corporate finance;capital allocation;capital structure;cost of capital"),
  ("Valuation","Stable","valuation;dcf;enterprise value"),
  ("Cost, pricing and profitability management","Stable","cost management;costing;profitability;contribution margin"),
  ("Budgeting, forecasting and FP&A","Stable","budgeting;financial forecasting;fp&a;planning and analysis;planning & analysis;financial planning and analysis"),
 ],
 "Investment and capital markets": [
  ("Investment management and portfolio theory","Stable","investment management;portfolio management;asset management;wealth management;investment advis;personal finance;wealth advis;personal financial planning;financial planner;asset allocation;investing;investment products?;securities industry;securities market;securities analysis"),
  ("Private equity and venture capital","Stable","private equity;venture capital;vcpe;growth equity;lbo"),
  ("Capital markets, debt and equity raising","Stable","capital market;ipo;debt market;equity raising;fund raising;fixed income;bond market"),
  ("Real estate finance and investment","Stable","real estate"),
  ("Alternative investments and hedge funds","Stable","alternative investment;hedge fund;commodit"),
 ],
 "Risk, treasury and financial regulation": [
  ("Financial risk management","Stable","financial risk;market risk;credit risk;risk management framework;quantitative finance;derivative;financial engineering"),
  ("Treasury, liquidity and working capital","Stable","treasury;liquidity;working capital;cash management"),
  ("Banking strategy and regulation","Stable","banking;basel;bank management;financial regulation"),
  ("Insurance and actuarial management","Stable","insurance;actuar;reinsurance"),
  ("Forensic accounting, fraud and financial crime","Stable","forensic;fraud;money launder;financial crime"),
 ],
 "Fintech and AI in finance": [
  ("Fintech, digital payments and embedded finance","Transformed","fintech;digital payment;embedded finance;upi;neobank;financial inclusion"),
  ("AI in finance: credit, trading and risk models","New","ai.*financ;financ.*ai;ai.*credit;algorithmic trading;ai.*risk model"),
  ("AI for the CFO and finance function","New","cfo.*ai;ai.*finance function;autonomous finance;finance automation"),
  ("Digital assets, CBDCs and crypto regulation","Stable","digital asset;cbdc;stablecoin;crypto regulat"),
 ],
}

T["Marketing, Sales & Customer"] = {
 "Marketing strategy and brand": [
  ("Marketing strategy for executives","Stable","marketing strategy;strategic marketing;marketing management;rural marketing;agri.input marketing;agri marketing;marketing leadership"),
  ("Brand management and positioning","Stable","brand;positioning"),
  ("Customer insight, segmentation and market research","Stable","customer insight;segmentation;market research;consumer behav"),
  ("Pricing strategy and revenue management","Stable","pricing;revenue management;monetis;monetiz"),
  ("Product management and product marketing","Stable","product management;product manager;product marketing;product lead;product development;product innovation;new product;ai products?;product strateg;building products"),
  ("B2B and industrial marketing","Stable","b2b;industrial marketing;business to business;b2b marketing;b2b sales"),
 ],
 "Digital growth and performance marketing": [
  ("Digital marketing and performance media","Transformed","digital marketing;performance marketing;paid media;sem;seo;customer acquisition"),
  ("Social, content and influencer marketing","Transformed","social media;content marketing;influencer"),
  ("Marketing analytics, attribution and MMM","Transformed","marketing analytic;attribution;marketing mix model;martech"),
  ("E-commerce, D2C and marketplace strategy","Transformed","e-commerce;ecommerce;d2c;direct to consumer;marketplace"),
  ("Customer lifecycle, retention and CRM","Stable","crm;customer lifecycle;retention marketing;loyalty;churn;customer relationship"),
 ],
 "AI in marketing": [
  ("Generative AI for marketing and creative","New","ai.*marketing;marketing.*ai;generative.*creative;ai content;ai.*brand"),
  ("AI-driven personalisation at scale","New","personalis;personaliz;recommendation engine;next best action"),
  ("AI and the future of search / discovery","New","ai search;answer engine;zero.click;conversational commerce"),
 ],
 "Sales and go-to-market": [
  ("Sales leadership and sales force management","Stable","sales leadership;sales team;sales force;sales management;sales strateg"),
  ("Key account management and enterprise selling","Stable","key account;strategic account;enterprise selling;solution selling"),
  ("Channel, distribution and route-to-market","Stable","channel;distribution;route to market;dealer;retail network"),
  ("Sales operations, enablement and AI in sales","Transformed","sales operation;sales enablement;revenue operation;ai.*sales;sales.*ai"),
  ("Negotiation for commercial outcomes","Stable","negotiat;bargaining;deal making"),
 ],
}

T["Operations, Supply Chain & Quality"] = {
 "Operations management": [
  ("Operational excellence and process improvement","Stable","operational excellence;process improvement;operations management;productivity;operations strateg;managing operations;global operations"),
  ("Lean, Six Sigma and quality management","Stable","lean;six sigma;quality management;tqm;kaizen"),
  ("Service operations management","Stable","service operation;service excellence;service design"),
  ("Manufacturing strategy and Industry 4.0 operations","Transformed","manufacturing;factory;plant;shop floor;smart manufactur"),
  ("Project management","Stable","project management;project planning;pmp;project delivery"),
 ],
 "Supply chain and logistics": [
  ("Supply chain strategy and design","Stable","supply chain;scm"),
  ("Procurement, sourcing and supplier management","Stable","procurement;sourcing;supplier;vendor management;purchasing"),
  ("Logistics, warehousing and distribution networks","Stable","logistics;warehous;freight;transportation;last mile"),
  ("Demand planning, inventory and S&OP","Stable","demand planning;inventory;s&op;sales and operations planning;forecast.*demand;demand forecast"),
  ("Supply chain resilience and risk","Transformed","supply chain resilience;supply risk;supply disruption"),
  ("AI and digital in supply chain","New","ai.*supply;supply chain.*(ai|analytic|digital);digital supply;supply chain analytic;operations analytic;control tower;procure.*(ai|digital|data)"),
 ],
}

T["People, Talent & Organisation"] = {
 "HR strategy and the CHRO agenda": [
  ("Strategic HR and business partnering","Stable","strategic hr;hr business partner;human resources? management;hr strategy;hrm;hr management;hr for (line )?managers;hr skills"),
  ("CHRO and HR leadership","Stable","chro;hr leadership;head of hr;people leadership"),
  ("Employee relations, labour law and industrial relations","Stable","industrial relation;labour law;labor law;employee relation;union"),
  ("Compensation, benefits and rewards","Stable","compensation;total reward;rewards? (strategy|management|system);employee benefit;payroll"),
  ("HR operating model and shared services","Stable","hr operating model;hr shared service;hr transformation"),
 ],
 "Talent, learning and workforce": [
  ("Talent acquisition and employer brand","Stable","talent acquisition;recruit;hiring;employer brand"),
  ("Performance management and appraisal systems","Stable","performance appraisal;performance review;performance management"),
  ("Learning, development and capability building","Stable","learning and development;l&d;capability building;training design"),
  ("Workforce planning and skills-based organisation","Transformed","workforce planning;skills based organis;skill taxonom;strategic workforce;future of work"),
  ("Leadership development and succession architecture","Stable","leadership development system;leadership development strateg;leadership development architecture;succession planning;talent pipeline;talent management"),
 ],
 "People analytics and AI in HR": [
  ("People analytics and HR data","Transformed","people analytic;hr analytic;workforce analytic;human capital analytic"),
  ("AI in HR: hiring, development and productivity","New","ai.*hr;ai.*hrm;hr.*ai;hrm.*ai;ai.*talent;ai.*recruit;ai in human resource;human resources?.*ai"),
  ("Employee experience and productivity measurement","Transformed","employee experience;productivity measure;engagement analytic"),
 ],
 "Culture, DEI and organisational behaviour": [
  ("Organisational culture and culture change","Stable","organisational culture;organizational culture;culture change;culture build"),
  ("Diversity, equity and inclusion","Stable","diversity;equity and inclusion;dei;inclusion;inclusive leader"),
  ("Women's leadership and gender in the workplace","Stable","women;gender;female leader"),
  ("Organisational behaviour and motivation","Stable","organisational behaviour;organizational behavior;behavioural science;behavioral science;behavioural econom;nudge"),
  ("Power, politics and influence in organisations","Stable","power and politic;organisational politic;influence without authority;influencing stakeholder;influencing your stakeholder;influencing skill;executive influence;selling ideas;influence others"),
 ],
}

T["Governance, Risk & Legal"] = {
 "Board governance": [
  ("Board effectiveness and director duties","Stable","board effectiveness;board director;corporate director;board member;board leadership;high.performance board;board best practice;board readiness;corporate governance;boards that lead;company director;independent director;women on boards?;boards? of directors"),
  ("Board committees: audit, remuneration, risk, nomination","Stable","audit committee;remuneration committee;nomination committee;risk committee"),
  ("Chair, CEO-board relationship and board dynamics","Stable","chairman;board dynamic;ceo.*board"),
  ("Board oversight of strategy, technology and AI","New","board.*strateg;board.*technolog;board.*digital;board.*ai"),
  ("Governance in family, state-owned and private companies","Stable","family business governance;state owned;psu governance;private company board"),
 ],
 "Enterprise risk and compliance": [
  ("Enterprise risk management","Stable","enterprise risk;risk governance;erm"),
  ("Internal audit, controls and assurance","Stable","internal audit;internal control;assurance"),
  ("Compliance, ethics and integrity programmes","Stable","compliance;business ethic;integrity;anti.corruption;whistleblow"),
  ("Reputation and stakeholder risk","Stable","reputation;stakeholder risk;crisis communication"),
 ],
 "Business law and regulation": [
  ("Commercial contracts and contract management","Stable","contract management;commercial contract;contract law;commercial law;contracting;contracts;legal leadership;corporate law;business law"),
  ("India regulatory stack for boards: DPDP, BRSR and RBI AI","New","dpdp.*board;brsr.*board;free-ai;india regulatory stack;indian compliance for board"),
  ("Competition, antitrust and sector regulation","Stable","competition law;antitrust;regulatory affair;sector regulat"),
  ("Insolvency, bankruptcy and dispute resolution","Stable","insolvency;bankruptcy;ibc;arbitration;dispute resolution;mediation"),
  ("Intellectual property and technology law","Transformed","intellectual property;patent;ip strategy;technology law"),
 ],
}

T["Innovation & Entrepreneurship"] = {
 "Innovation management": [
  ("Innovation strategy and portfolio","Stable","innovation strategy;innovation management;innovation portfolio;driving growth through innovation;managing innovation;innovation leadership;leading innovation;disruptive innovation;culture of innovation;innovation by design"),
  ("Design thinking and human-centred design","Stable","design thinking;human centred;human centered;human-centred design"),
  ("R&D management and technology commercialisation","Stable","r&d management;research and development;technology commercialis;technology transfer"),
  ("Corporate venturing and open innovation","Stable","corporate ventur;open innovation;innovation ecosystem;startup accelerator;corporate accelerator"),
  ("Intrapreneurship and new business building","Stable","intrapreneur;venture building;new business build;corporate startup"),
 ],
 "Entrepreneurship": [
  ("Starting and scaling a venture","Stable","entrepreneur;startup;start-up;founder;new venture"),
  ("Fundraising and investor readiness","Stable","fundrais;investor readiness;pitch deck;investor pitch;seed fund;seed stage;term sheet"),
  ("Family business succession and next-generation owners","Stable","family business;family enterprise;family firm;family owned business;families in business;next.generation (owner|family);succession.*family;family business management"),
  ("Social entrepreneurship and impact ventures","Stable","social entrepreneur;social enterprise;impact ventur;non.?profit;ngo"),
  ("Franchising, SME growth and business ownership","Stable","franchis;sme;small business;msme;owner manager"),
 ],
}

T["Sustainability, ESG & Climate"] = {
 "Sustainability strategy": [
  ("Sustainability and ESG strategy for the enterprise","Transformed","sustainab;esg;environmental social"),
  ("Net-zero transition and decarbonisation","New","net zero;net-zero;decarbonis;decarboniz;carbon;emission;climate transition"),
  ("Circular economy and sustainable operations","Stable","circular economy;waste;sustainable operation;resource efficiency"),
  ("Sustainable finance, green bonds and climate risk in finance","Transformed","sustainable finance;green bond;climate risk;transition finance;esg investing;impact finance;impact investing;finance for impact"),
 ],
 "ESG disclosure and governance": [
  ("ESG reporting, assurance and CSRD/BRSR compliance","New","esg report;csrd;brsr;sustainability report;esg disclosure;issb"),
  ("Climate risk governance and board oversight of ESG","New","climate governance;board.*esg;tcfd"),
  ("Social impact, CSR and community investment","Stable","csr;corporate social responsib;community investment;social impact"),
  ("Energy transition and renewables business","Transformed","energy transition;renewable;solar;hydrogen;power sector"),
 ],
}

T["Public Policy, Government & Infrastructure"] = {
 "Public policy and governance": [
  ("Public policy design and analysis","Stable","public policy;policy design;policy analysis;policy making"),
  ("Regulatory economics and market design","Stable","regulatory economic;market design;tariff setting;utility regulation"),
  ("Governance for civil servants and elected representatives","Stable","civil servant;public administration;legislator;elected representative;bureaucra"),
  ("Digital public infrastructure and e-governance","New","digital public infrastructure;e-governance;digital identity;aadhaar;govtech"),
  ("Public-private partnerships and infrastructure finance","Stable","public private partnership;ppp;infrastructure finance;project finance"),
 ],
 "Sector and development policy": [
  ("Urban management and smart cities","Stable","urban;smart cit;municipal"),
  ("Agriculture, rural and food systems policy","Stable","agricultur;rural development;rural;food system;agri business;agribusiness"),
  ("Education policy and institutional leadership","Stable","education policy;school leadership;higher education management;academic leadership;education leader;educational leader"),
  ("Defence, security and strategic affairs","Stable","defence;defense;national security;military"),
 ],
}

T["Healthcare & Life Sciences"] = {
 "Healthcare management": [
  ("Hospital and healthcare operations management","Stable","hospital;healthcare management;health care management;clinic management;patient flow"),
  ("Healthcare strategy, payers and providers","Stable","healthcare strategy;health care strategy;payers?;healthcare provider;health system;health insurance"),
  ("Public health policy and programme management","Stable","public health;health policy;epidemio;immunis"),
  ("Digital health, health analytics and AI in medicine","New","digital health;health analytic;ai.*health;telemedicine;health tech"),
 ],
 "Life sciences and pharma": [
  ("Pharmaceutical and biotech management","Stable","pharmaceutical;pharma;biotech;life science"),
  ("Medical device and diagnostics business","Stable","medical device;diagnostic;medtech"),
  ("Clinical leadership for doctors and care teams","Stable","clinical leadership;physician leader;doctor.*management;nursing leadership"),
 ],
}

T["Sector-Specific Management"] = {
 "Regulated and asset-heavy sectors": [
  ("Banking, financial services and insurance sector management","Stable","bfsi;banking sector;insurance sector;financial services management"),
  ("Energy, utilities, oil and gas management","Stable","oil and gas;utilit;power utility;mining industry;mining sector;metals and mining;mining compan;petro"),
  ("Infrastructure, construction and real estate development","Stable","construction;infrastructure management;real estate development"),
  ("Telecom, media and entertainment management","Stable","telecom;media management;entertainment;broadcast;ott"),
  ("Transport, aviation, shipping and railways","Stable","aviation;airline;shipping;maritime;railway;port"),
 ],
 "Services and consumer sectors": [
  ("Retail and consumer goods management","Stable","retail management;fmcg;consumer goods;grocery"),
  ("Hospitality, travel and tourism management","Stable","hospitality;hotel;tourism;travel management"),
  ("IT services, GCC and global capability centre leadership","New","global capability cent;gcc;global in.house cent;shared service cent;it services"),
  ("Influencing global headquarters from a captive centre","New","headquarters influence;hq relationship;mandate expansion;captive centre;value migration"),
  ("Professional services and consulting management","Stable","consulting;professional service;advisory firm;partner track"),
  ("Sports, arts and luxury management","Stable","sport;luxury;art management;arts management;fashion;creative and cultural business;cultural business;sports business;sports management"),
 ],
}

T["Personal Effectiveness & Communication"] = {
 "Executive presence and communication": [
  ("Executive presence and personal brand","Stable","executive presence;personal brand;gravitas;leadership presence;personality development;etiquette;grooming"),
  ("Business storytelling and narrative","Stable","storytelling;narrative;story"),
  ("Public speaking, presentation and boardroom communication","Stable","public speaking;presentation skill;boardroom communication;speak with impact;communication skill;communication effectiveness;business communication;leadership communication;communication strateg;corporate communication"),
  ("Business writing and structured communication","Stable","business writing;written communication;structured thinking;structured communication"),
  ("Media, investor and stakeholder communication","Stable","media training;investor relation;stakeholder communication;spokesperson"),
  ("Cross-cultural and global communication","Stable","cross.cultural;intercultural;global communication"),
 ],
 "Personal productivity and judgment": [
  ("Decision-making, biases and behavioural judgment","Stable","decision making;decision-making;bias;heuristic;judgment and decision;judgement;decision science"),
  ("Critical thinking and problem solving","Stable","critical thinking;problem solving;structured problem;first principle"),
  ("Time, attention and personal productivity","Transformed","time management;productivity skill;personal effectiveness;attention management"),
  ("Networking, influence and career strategy","Stable","networking;career strategy;career transition;personal growth;self leadership"),
  ("Emotional intelligence and self-awareness","Stable","emotional intelligence;self.awareness;eq;mindful leader"),
  ("Conflict management and mediation skills","Stable","conflict management;conflict resolution;mediation skill;workplace conflict;managing conflict;conflict"),
 ],
}

T["General Management (Integrative)"] = {
 "Comprehensive general management": [
  ("General management programmes for senior leaders","Stable","general management;advanced management programme;senior management programme;management programme for;executive management programme;management development programme"),
  ("Mini-MBA and business fundamentals for specialists","Stable","mini mba;business fundamental;business essentials;management essentials;business acumen;foundations for business"),
  ("Cross-functional business simulation and integration","Stable","simulation;capstone;integrative;business game"),
  ("Owner-manager and promoter programmes","Stable","owner manager;promoter;business owner programme;family owned business programme"),
 ],
}

# Sub-themes filed under a different theme from the one they were numbered in.
# Their topic ids do not change, because data/demand_all.csv, saved links and
# the snapshots refer to topics by id. AI-era strategy moved to AI, Data & Digital
# on 24 Nov 2026, so that every programme whose subject is AI is counted under AI.
MOVED={"AI-era strategy":("AI, Data & Digital","AI foundations for leaders")}  # sub-theme -> (theme, placed after)

# A topic in these sub-themes counts a keyword match only when the same text also
# matches this pattern (scripts/classifier.py). "AI teams" is about leading people
# with AI, not about AI agents as a technology; "AI in marketing" needs marketing.
REQUIRES={
 "Leading human-AI organisations":r"lead|manag|team|workforce|workplace|employee|organi[sz]|human|people|\bwork\b",
 "AI in marketing":r"marketing|brand|customer|consumer|advertis|creative|content|sales|persuasion|personalis",
}

rows=[]
ti=0
for theme,subs in T.items():
    ti+=1; si=0
    for sub,topics in subs.items():
        si+=1; pi=0
        for (topic,ai,kw) in topics:
            pi+=1
            rows.append(dict(
                theme_id=f"T{ti:02d}", theme=theme,
                subtheme_id=f"T{ti:02d}.S{si:02d}", subtheme=sub,
                topic_id=f"T{ti:02d}.S{si:02d}.P{pi:02d}", topic=topic,
                ai_era_flag=ai, keywords=kw, requires=REQUIRES.get(sub,'')))
_theme_id={r['theme']:r['theme_id'] for r in rows}
for sub,(theme,after) in MOVED.items():
    moving=[r for r in rows if r['subtheme']==sub]
    assert moving, f"MOVED names a sub-theme that does not exist: {sub}"
    rows=[r for r in rows if r['subtheme']!=sub]
    for r in moving: r.update(theme=theme,theme_id=_theme_id[theme])
    at=max(i for i,r in enumerate(rows) if r['subtheme']==after)+1
    rows[at:at]=moving
os.makedirs(str(_R),exist_ok=True)
with open(str(_R/'taxonomy.csv'),'w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0].keys()),quoting=csv.QUOTE_ALL); w.writeheader(); w.writerows(rows)
print("themes",len(T),"subthemes",sum(len(v) for v in T.values()),"topics",len(rows))
import collections
print(collections.Counter(r['ai_era_flag'] for r in rows))

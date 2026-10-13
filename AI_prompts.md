# Homework 5 — AI Prompts Log

A log of the prompts I typed to the AI assistant, one section per problem.

---

## Problem 1: Vibe Coder Prompts

**Prompt:**

> Problem 1: Vibe Coder Prompts.Today we will be working in homework 5 folder. Create an AI_prompts.md file there. This file is a log of what I type to you. Create one section per problem that will contain the problem # and title, the prompt i typed in my own words, and any follow up prompts if applicable

**Follow-up prompts:**

_None yet._

---

## Assignment Context (Campus Customs Multi-Agent Operations Team)

**Prompt:**

> For context for this assignment. We will be adding to the campus customs shop. We will create a multi-agent operations team that runs the shop. They will have open tickets land on a board: customer orders, rent, unpaid bills, discount requests, and anything else the shop needs to handle. We will build an MCP server, a FastAPI backent with a multiagent team, and a react dashboard so a human can watch the agents work and approve requests, The agent team will have full connectivity and any agent may delegate tasks to any oither agenbt for help. Throughout the assignment we will build:
> - Boss: reads every ticket, decides who works on it, makes final decisions
> - Inventory: checks stocks by SKU and size, spots shortfalls, and figiures out which vendor can restock
> - Accounting: watches cash adn invoices, checks margins, and preps payments or purchase orders for human approval.
> - Facilities: handles the shop space including leases, rent, etc
> customer service: drafts messages for customers.
> I will add a data file to the folder, unzip it.
> Rules of the shop:
> - desk.date_today is today for the shop and this date is to be used to determine if anything is overdue
> - Vendor lead times come from the vendors table
> - A vendor will not ship new product whilke they have an openb unpaid invoice
> - Human approval is required for any paynments. This will lose points if it is not done properly. If a payment is made, ensure to update the relevant table
> - IF there is not enough cashm the pay tool must refuse to pay, there cannot be negative balances,.
> - Cash only goes out in this assignment, we did not model revenue so no money shoudlk come in,.
> - Before a full run to resolve the tickets, ensure to reset the database to original values,
> - NEVER email customers of call real vendors. This is a mock assignment and all drafts stay on the board>
> Use the Portkey api key in the .env folder in the root for ai calls. Use only gpt-6-luna for every agent. Do not use any other model or points will be lost. The final output will be a submission to a public github repo. Dont do any of this yet except the data file as I will walk you through step by step. This si only for context

_(This prompt was first sent, interrupted, and then re-sent in full; the complete version is logged above.)_

---

## Problem 2: Study the Campus Customs database

**Prompt:**

> Problem 2: Study the Campus Customs database
> Open the data/campus_customs.db and look through every tavble and its fields. Copy the original file to data/campus_customs_new.db and later problems will update that working copy. Study the three open tickets so you see how they will link to other tables. Start output/harness.md file and for each table list the fields and one short line on why that tiable matters to the agents. We will keep building on this harness file in later problems

**Follow-up prompts:**

_None yet._

---

## Problem 3: Build the MCP server

**Prompt:**

> Problem 3: Build the MCP server
> Write an MCP server in mcp_server/ using FASTMCP. This will communicate with data/campus_customs_new.db. This does not need to be connected or ranb in this problem. Every agent in this assignment will use the tools in this mcp server. We will add more tools to it later. FOr now write three tools that you know you will need for the tickets in the database. Keep the names clear. Never invent any data. Only use information provided in the database. In output/harness.md list each of the three mcp tools,. FOr ewach tool include:
> - which table it reasds
> - Which ticket it helops unlock (101,102,103)
> - one sentence on why that tool is the right one for that ticket. Make sure lines are detailed and tied to the ticket. Vague lines like "reads inventory" will get low points
> Add a short mcp_server/README.md file that expolainbs what the MCP server is for. which db file it uses and the three tools it has

**Follow-up prompts:**

> 2 sentences is fine

---

## Problem 4: Add the MCP server to Vibe Coder and test each tool

**Prompt:**

> Problem 4: Add the MCP server to vibe coder and test each tool. Add the MCP server to this project so you can call the tools. Save the connection JSON text in .mcp.json at tghe project root or however you save local mcp server lists. When you are connected, I will test each tool. Tell me how i cant test them

**Follow-up prompts:**

> I will now test each tool. Save the prompt I gave you, the tool name, and tool output which must match values in data/campus_customs_new.db. Record this in output/mcp_smoke.json when I start

> we will now test the mcp server as a continuation of problem 4
> Through the campus-customs MCP server, call check_stock for CC-TEE-WHITE size S, quantity 1

> Through the campus-customs MCP server, call check_stock for CC-HOOD-NAVY size M, quantity 20

> Through the campus-customs MCP server, call check_vendor_status for vendor 1

> Through the campus-customs MCP server, call check_vendor_status with no vendor ID

> Through the campus-customs MCP server, call check_rent_due for lease 1

> Through the campus-customs MCP server, call check_stock for CC-HOOD-NAVY size XXL

> All 6 MCP tool tests passed. Log my test prompts as follow-up prompts under Problem 4 in AI_prompts.md, and add a short “Testing” section to mcp_server/README.md listing the 6 test calls and their results. Along with the format i specified before

---

## Problem 5: Build the agent team and grow the MCP tools

**Prompt:**

> Problem 5: Build the agent team and grow the MCP tools
> Build the agentic team for campus customs using pydanticAI. Build the boss, inventory, accounting, facilities, and customer service. Include prompts, models, agent loops so they can delegate work to each other with full connectivity. Put the agent prompts in backend/prompts/ - one file per agent. Put data types in backend/models.py, and the agent files under backend/ Make sure the five roles are clear. Use Portkey api key and only gpt-6-luna for every agent.
> All agents:
> - Today is desk.date_today not the real date
> - Only use facts from mcp tools, they they dont have the data flag it
> - never contact customers or vendors, everything stays as drafts on trhe board
> - Team roster: any agent can delegate to another
> - limit tool calls and delegations per ticket, escalate if stuck
> Boss:
> - reads tickets and classifies. routes with speciic tasks that include ids. checks that findings trace back to tools and makes last call. Sets a status (resolved, await approval, blocked, need human). can recommend payments but never approves or makes. sets priorities when cash cant cover all expenses.
> Inventory: check_stock by sku + size+ qty and report shortfolls. Sku or size nopt exist report it. On a shortfall check_vendor_status to find who can restock. Lead time comes from the vendors table, arrival = date_today + lead time. A vendor with unpaid invoice wont ship --> hand off to accounting. Recommends vendors NEVER places orders.
> Accounting: watches cash, invoices, and margins. payment flow: verify bill --> chec cash --> request human approval --> pay only after approval --> update payments, invoice/rent and cash tables.
> not enough cash -> refuse, never have negative balances or partial payments. no revenue, never count incoming funds. discounts show the margin impact and flag selling below cost. purchase orders spend cash so they need approval.
> facilities: check_rent_due for the lease amount, payee, due date. upcoming/due today/overdue measured against date_today. Always hands ret to accounting for cash check and approval. never pays, renegotiates, or contacts landlord
> customer service: drafts only saved to the board never sent. uses only facts confirmed by inventory or boss. draft structure: thank customer -> answer->honest about delays -> next step short and freindly. nevr shares internal info like cash, unpaid invoices, marginsm blockd vendors. never promises dates, discounts, or stock that havent been confirmed

**Follow-up prompts:**

> Make sure to add any tools the agents need to mcp server so they can work on open tiockets. shop facts come from the mcp server over data/campus_customs_new.db never invent a scond shop tools layer that bypasses mcp. Wire the agents the they append to output/audit_trail.json as they run for each agent loop step, make sure to record enough to audit latter. Always add to the file do not wipe it. In output/harness.md list each agent and each MCP tool including ones added now along with which table the tool uses. Also add a short safety section whcih includes guardrails a real business would want when agents touch customers and real money, and limits to keep token use in check. Update mcp_server/README.md so the tool list matches. ALSO remember, this is to be all done here, Nver contact anyone or place any orders it is a mock assignment

> where are the tickets stored

> what is each ticket

---

## Problem 6: Plan the three tickets

**Prompt:**

> Problem 6: Plan the three tickets
> Before we wire the backend, I will write down what I expect the team to do for each open ticket. Build output/desk_tickets.html which will be a page that can be double clicked with one tab per ticket. Also, add empty Cash and Reflection tabs for later problems. Leave these with a "coming later" note. On each ticket tab I will fill the expected section only. create an empty Actual section that will be filled once we run the agents.

**Follow-up prompts:**

> For the expected resul;ts in the desk tickets html replace what is there with my writing. Make it fit into the sections you have: Ticket 101: Tauhid’s tee
>
> The Boss should send this ticket to the Inventory agent first, since it’s a customer order and the first thing that we need to know is whether we have the shirt avaliable in stock. Inventory should find that we have zero size S whites, and when it checks the vendor, it will be blocked by unpaid invoice 501. Inventory will then hand that off to Accounting, which will check that we have enough cash to pay the invoice and will ask a human to approve paying the $840 required. Once that’s approved and paid, the Accounting agent can set up a small restock order for one tee ($8), which also needs manual human approval. Finally, the Customer Service agent will draft a note to Tauhid saying the tee is on backorder and provide an estimate for roughly when it should arrive. Facilities agent shouldn’t be involved for this ticket.
>
> Tools I expect to be used: check_stock, check_vendor_status, the cash and payment-approval tools, the pay tool, and the draft tool.

> For Ticket 102: Rent
>
> This ticket goes to the Facilities agent first because it’s about the lease. The facilities agent should confirm that we owe Elm City Properties $2,400 for rent, due in two days Therefore, it isn’t late yet. The agent then passes that to the Accounting agent, which checks cash reserves and asks a human to approve the payment. After human approval, the rent gets paid and the tables update with an outflow of cash. Inventory and Customer Service agents will not be involved as they have nothing to do here, due to this not being a customer message.
>
> Tools I expect to be used: check_rent_due, the cash and payment-approval tools, and the pay tool.

> For Ticket 103: Yale AI Club hoodies
>
> The Inventory agent gets delegated first again. Before determining price, we need to know how many units we can actually deliver. The agent should find only 8 of the 20 in stock, and restocking the other 12 runs through the same blocked vendor as ticket 101. The accounting agent then looks at the discount. Each hoodie costs us $22 and sells for $58, so any discount has to stay above the cost of $22. Restocking 12 items would cost $264. The discount is a human decision, so the Boss should flag it for approval rather than decide it alone. The human would then decide if to have a discount and the amount of discount. The Customer Service agent then drafts a reply saying 8 are ready now and the rest depend on a restock, without promising a price yet. Facilities agenty isn’t needed for this ticket.
>
> Tools I expect to be used: check_stock, check_vendor_status, the cash tools, and the draft tool.

---

## Problem 7: Backend routes

**Prompt:**

> Problem 7: Backend routes 
> The reach frontend dashboard to be build in the next problem needs to have a backend to call. In backend/main.py, use FastAPI and add routes thatr do the following:
> - Return the three tickets and whether each is open or resolved
> - Take a ticket id and run your agent team on that ticket
> - Return recent agent events: what each agent saidf and which tools their used to refresh the board
> - Approve a payment or purchase after the human clicks approve. Agents only prepare to pay, only human approval can change cash
> - return the current checking balance from cash_accounts
> - reset the database to the original values when I want a fresh run
> From the backend/ folder, start the server with: uvicorn main:app --reload --port 8000
>
> This turns on the backend at http://localhost:8000 so the frontend dashboard can call those routes. In output/harness.md, list each route in one line saying what URL does what

**Follow-up prompts:**

_None yet._

---

## Problem 8: Agent dashboard

**Prompt:**

> Problem 8: Agent dashboard
> Buikld the frontedn dashboard in frontend/ with React + Vite + TypeScript. This page needs to call the routes you built in Problem 7. The board needs to list all three tickets. Allow me to pick one ticket and start the agent team on it. The page needs to show each agent and what they are saying and doing while the ticket runs. Mark the ticket as resolved once the run finishes. Then a short summary of what each agent did should be shown on the ticket. Human approval is REQUIRED for any purchase or payment. The checking balance shoukld be shownb and it should decrease after an approved payment. Build the dashboard in yale style we built for the previous homework. Make the boss Darth Vader and the other agents various characters from starwars. 
>
> The front end should talk to the backend at http://localhost:8000. On the backendm, allow the Vite page origin (usually http://localhost:5173) so the browser ius allowed to call these routes. Start the dashboard with: npm run dev. This needs to open the react desk in the browser so you can pick tickets and watch agents. Write output/design.md with what you chose fior the dashboard look (layout, how agents read, how resokved tickets and cashg show uo) and why. Include creative chiocuies that make it feel special and what humans woukldf want to use

**Follow-up prompts:**

_None yet._

---

## Problem 9: Resolve the tickets

**Prompt:**

> Problem 9: Resolve the tickets
> Before we test teh agents on a full run over the three tickets. Reset the working database data/campus_customes_new.db again so we start with clean data. Make sure the starting checking balance is correct. Then, run all three tickets on the board untill each is resolved. Again remember what the agents need my approval for and remember that nothing is to leave this website. No real emails or payments this is a draft mock project. 
> Then open output/desk_tickets.html from problem 6 and on each ticket tab, fill in the actual section from this run. Make sure to include which agents worked, what work they delegated, and what tools were used. Make sure to keep the expected section so i can compare them. 
> On the Cash tab of the output/desk_tickets.html, itemize the money:
> - starting checking balance post reset
> - for each ticket: how cash changed, when the ticket resolved, and why (which pay/purchase, $ amount
> - ending checking balnce must match cash_accounts in the working database
> Wriong cash math loses points even if board shows every ticket resolved. Make sure to save:
> - output/resolved_tickets.json: for each ticket: id, final status, short outcome, what each agent contributed, and any human approvals
> - output/resolved_board.html: a page that can be doubkle clicked with a screenshot of the React board for each resolved ticket.
>
> Append real runs to output/audit_trail.json. Finish output/harness.md so it covers tables, MCP tools, the five agents, API routes, the dashboard, and safety rules

**Follow-up prompts:**

> (Answers to approval questions) Approve #1 Invoice 501 — $840 and #2 Rent — $2,400; sign as "Store manager"; for any new requests after re-running: "Ask me again".

> (Answer) Approve request #3, PO for 1 CC-TEE-WHITE size S, $8.00, as "Store manager".

> how do i decide the discount. I dont see anywhere on the webpage

> Build it to have options of discounts with some info about how they would impact profitability. ex how much the rev-discount price would be

---

## Problem 10: Reflection

**Prompt:**

> For the desk tickets HTML in the reflection tab write the following make sure the writing makes sense and falls into the right catagories. fix spelling and gramatical errors before you add it.
> Section 1, how would you evaluate the performance of the agents on each ticket and why? I judged each ticket on whether the facts were right, whether the money rules held, and how much work it took. Ticket 102 for rent was the strongest. Facilities found 2,400 due on 9/02. And the accounting requested approval without paying. The final run took only four tool calls, and run two escalated because the rent tool couldn't see the payment. But the boss safely asked a human instead of requesting a second payment. For ticket 101, the t-shirt, it was correct but inefficient. Every fact was correct with zero in stock, and the vendor was blocked by invoice 501. And it took but it took four runs. And 55 tool calls for only one $8 t-shirt. Accounting repeated checks inventory had already done and customer service wrote four drafts. For ticket 103 hoodies, it was a good judgment but weak on cash. No agent invented discount and the margin math was correct, but no agent ever checked the 12 hoodie restock, the 246 cost, more than the $152 left in checking. So overall, the three payments were approved by a human before any cash moved. And the weak spots were repeated work and no planning of cash access across tickets. For section two, this is for how for each ticket, how did the actual compare to the expected plan? We wrote earlier. So for ticket 101, the agent path in both approvals matched my plan. It took four runs instead of one because the team stops at each approval. And the dashboard paid the bills when I clicked approve, not uh, accounting agent doing it on its own. So for 102, it also matched my plan. Uh, facilities and accounting, and then my approval. And then the cash went down by 2,400. This took three runs because the rent tool's blind spot. And for ticket 103, the stock count, the 22 cost floor, and send the discount to the human all matched. The only difference was that the $246 restock was never requested or costed. And the discount ends as needs human rather than an approval because approvals only cover payments. Section three, what would have been simpler as one agent with tools and why. So ticket 102 would have been simpler. It's a fixed chain of three tools that check rent, check cash, and request approval. Facilities only called one tool and handed it off, and then accounting called the same tool again. One agent would take about four calls instead of 10 that were done. And the safety comes from tool permissions and human approval, not from having separate agents. So one agent would have been just as safe. Section 4, 3 new problems as team could solve with the tools I built. Uh, the first is an order for 30 Crest mugs, mugs are at zero in stock in their vendor, the Elm City Gifts, has no unpaid invoices. Inventory finds the shortfall, accounting requests a $105 approval. Uh, which fits in with the $152 remaining in the cash balance. Customer service drafts a reply with the expected September 3rd arrival. Uh, the second thing would be October rent with only $152 left in checking. Facilities report that there's $2,400 due on October 2nd. And the approval tool refuses because the cash can't cover it. And the boss marks the ticket as blocked. Third, the AI club counteroffers $45 per hoodie. Accounting's discount tool shows the price is still above the $22 cost. And I report the decision of the dashboard and the customer service drafts the offer. Section 5, three new problems this team could not solve and what it would need. Uh, so firstly, collecting payment from customers. There's no tool that records a sale or adds any cash or is allowing any revenue inflow. Uh, what would be needed would be a record sale tool and a receive stock tool and potentially a sales agent. Number two, sending orders and messages. Everything remains a draft and no tool can contact anyone. So for this, we would need a send purchase order and send message tools behind human review. And a communications agent. Thirdly, planning cash ahead. The cash tool only shows today's balance and the boss works at one ticket at a time. So something we could use would be a need would be a cash forecast tool in the treasury agent that ranks bills across tickets.
> Clean it up before putting in reflection. Make sure to add units based on context.

**Follow-up prompts:**

_None yet._

---

## Problem 11: Publish the repo (README, .env.example, .gitignore, GitHub)

**Prompt:**

> Create a README.md at the project root that explains, step by step: what the project is (Campus Customs multi-agent ops desk: MCP server, FastAPI backend with 5 agents, React dashboard), setup (create venv, pip install -r requirements.txt, copy .env.example to .env and add a Portkey key), how to copy data/campus_customs.db over data/campus_customs_new.db for a clean run, how to start the MCP server, how to start the FastAPI backend (cd backend; uvicorn main:app --reload --port 8000), how to start the React board (cd frontend; npm install; npm run dev, opens http://localhost:5173), and how to reset the database before a full three-ticket run (dashboard Reset button, POST /reset, or python -m backend.reset_db). Note that .mcp.json uses the Windows venv path and Mac/Linux users should change it to .venv/bin/python. Also point to the output/ files and what each one is. Keep it short and clear.
> Create .env.example with PORTKEY_API_KEY= and no real value.
> Check .gitignore covers .env, .venv/, pycache/, node_modules/, frontend/dist/, and .DS_Store. Make sure it does NOT ignore data/campus_customs.db or data/campus_customs_new.db, because both must be in the repo.

**Follow-up prompts:**

> do not push to github yet but when you do, dont include data.zip

> (Screenshot of the required hw5/ layout: AI_prompts.md, requirements.txt, .env.example, .gitignore, .mcp.json, README.md, data/{campus_customs.db, campus_customs_new.db}, mcp_server/{server.py, README.md}, frontend/, backend/{main.py, models.py, prompts/{boss, inventory, accounting, facilities, customer_service}.md}, output/{harness.md, mcp_smoke.json, desk_tickets.html, design.md, resolved_tickets.json, resolved_board.html, audit_trail.json, github_url.txt})
> Initialize git if needed, stage everything, and show me git status so I can check the file list against the required layout before committing. Then make the first commit.
> Stop there and ask me for the GitHub repo URL. Do not push until I give it to you. After I do, push to main and save the URL in output/github_url.txt, then commit and push that file too.
> Log this prompt and any follow-ups under Problem 11 in AI_prompts.md.
> Also check that structure is correct

> Ensure that only the specified files are pushed. Files should only be in Homework 5 folder of MGT 409 folder. Also ensure that no real secrets are pushed
> https://github.com/Rsofman/mgt409-hw5.git

> (Answer) Keep needed files: push the layout plus the backend files the app needs to run; drop only .gitkeep.

import {render,fireEvent,screen,waitFor} from "@testing-library/react";
import {expect,it,vi} from "vitest";
import * as api from "../lib/api";
import {MultiResponse} from "../components/MultiResponse";
import {OpponentIntelligence} from "../components/OpponentIntelligence";
import type {StrategyResult} from "../lib/strategy-types";
import sample from "./strategy-fixture.json";

it("selecting observed evidence requires explicit adoption of a policy hypothesis",async()=>{
  const adopt=vi.fn();
  vi.spyOn(api,"requestJson").mockResolvedValue([{id:"player-1",name:"Example",source:"manual",
    hands:30,override:null,provisional:"lp",evidence:"Test evidence",metrics:{},history:[]}]);
  render(<OpponentIntelligence onHypothesis={adopt}/>);
  fireEvent.click(screen.getByText("Opponent observations"));
  const button=await screen.findByRole("button",{name:"Use this label as a modeling hypothesis"});
  expect(adopt).not.toHaveBeenCalled();
  fireEvent.click(button);
  expect(adopt).toHaveBeenCalledWith("lp");
});

it("sends explicit sensitivity policies without observation data and clears stale numbers on edit",async()=>{
  const strategy=sample as unknown as StrategyResult;
  const mock=vi.spyOn(api,"requestJson").mockImplementation((async(path:string)=>{
    if(path.endsWith("-policy"))return {"turn/check":{AcAd:{check:.5,"bet@275":.5}}};
    return {assumptions:"Fixed test policy",results:[{name:"Base",decisions:[],changes:[],
      root:{equilibrium_ev:1,baseline_model_ev:1,response_model_ev:2,gain:1,equilibrium_cost:0}}]};
  }) as typeof api.requestJson);
  render(<MultiResponse strategy={strategy} profile="tag"/>);
  await waitFor(()=>expect(screen.getByLabelText("Opponent combo")).toHaveValue("AcAd"));
  fireEvent.click(screen.getByLabelText(/Compare opening rates/));
  fireEvent.click(screen.getByRole("button",{name:"Calculate full-tree response"}));
  expect(await screen.findByText("Root gain 1.000")).toBeInTheDocument();
  const payload=mock.mock.calls.find(([p])=>p.endsWith("/multistreet"))![1] as {hypotheses:{opening_bet:number}[]};
  expect(payload.hypotheses.map(h=>h.opening_bet)).toEqual([.4,.25,.55]);
  expect(payload).not.toHaveProperty("observations");
  fireEvent.change(screen.getByLabelText("Opening turn bet (%)"),{target:{value:"30"}});
  expect(screen.queryByText("Root gain 1.000")).not.toBeInTheDocument();
});

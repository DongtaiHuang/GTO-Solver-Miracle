import {readFileSync} from "node:fs";
import path from "node:path";
import {fireEvent, render, screen} from "@testing-library/react";
import {expect,it,vi} from "vitest";
import {TrainerRiverFeedback} from "../components/TrainerRiverFeedback";
import * as api from "../lib/api";
import type {StrategyScenario} from "../lib/strategy-types";
import {gameState} from "./fixtures";
import {profileFixtures} from "./study-fixtures";

it("matches public trainer history, uses the villain's preset, and limits feedback to hero's combo", async()=>{
  const file=path.resolve(process.cwd(),"../backend/src/poker_lab/data/river_550.json");
  const {document}=JSON.parse(readFileSync(file,"utf8"))[0];
  const scenario:StrategyScenario=document.scenario;
  const game=gameState();
  Object.assign(game,{street:"river",board:scenario.board,pot:550,effective_stack:9750,opponents:Array(5).fill(profileFixtures[4])});
  game.players[0].cards=["Ad","Ac"];
  game.history=scenario.history.map((e,i)=>({sequence:i+1,street:e.street as typeof game.street,
    seat:game.players.find(p=>p.position===e.position)!.seat,name:e.position,action:e.action,
    chips:e.amount??0,raise_to:e.action==="raise"?e.amount:null}));
  const mock=vi.spyOn(api,"requestJson").mockImplementation((async (route:string)=>{
    if(route.endsWith("scenarios"))return {scenarios:[{solution_id:document.solution_id,scenario}]};
    return {opponent:{},decisions:[],message:"Calculated for test"};
  }) as typeof api.requestJson);
  const view=render(<TrainerRiverFeedback game={game}/>);
  fireEvent.change(await screen.findByRole("combobox"),{target:{value:document.solution_id}});
  expect(await screen.findByText("Calculated for test")).toBeInTheDocument();
  expect(mock).toHaveBeenCalledWith("/api/strategy/exploit",expect.objectContaining({profile:"lp",scenario}),expect.anything());
  view.rerender(<TrainerRiverFeedback game={{...game,history:game.history.slice(1)}}/>);
  expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  expect(screen.getByText(/No covered decision/)).toBeInTheDocument();
});

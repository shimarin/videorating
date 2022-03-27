#!/usr/bin/env -S deno run --allow-net --allow-read --allow-write --allow-env
import {parse} from "https://deno.land/std/flags/mod.ts";
import { DB,QueryParameter } from "https://deno.land/x/sqlite/mod.ts";
import { Application,Router,helpers } from "https://deno.land/x/oak/mod.ts";

const args = parse(Deno.args);
const HOSTNAME = args.h || undefined;
const PORT = args.p || 8000;

if (args._.length < 1) {
  console.log("DBfile must be specified.");
  Deno.exit(1);
}
//else
const db = new DB(args._[0] as string);

const router = new Router();
router
.get("/", (context)=> {
  const query = helpers.getQuery(context);
  let conditions = "";
  const params:QueryParameter[] = [];
  if (query.rating !== undefined) {
    conditions +=  " and rating=?";
    params.push(query.rating);
  }
  params.push(query.limit || 100);
  params.push(query.offset || 0);
  
  const rows = db.query("select filename,size,rating,mtime,objects.hash from files,objects where files.hash=objects.hash" + conditions + " order by size desc limit ? offset ?", params);
  const files:{filename?:string,size?:number,rating?:number,mtime?:number,hash?:string}[] = [];
  for (const [filename,size,rating,mtime,hash] of rows) {
    files.push({
      filename:filename as string,
      size:size as number,
      rating:rating as number,
      mtime:mtime as number,
      hash:hash as string
    });
  }
  context.response.type = "application/json";
  context.response.body = JSON.stringify(files);
})
.post("/:hash/rate", async (context)=> {
  const body = await (await context.request.body({type:"json"})).value;
  db.query("update objects set rating=? where hash=?", [body.rating, context.params.hash]);
  context.response.type = "application/json";
  context.response.body = JSON.stringify({rating:body.rating});
})
;

const app = new Application();
app.use(router.routes());

console.log("Starting server" + (HOSTNAME? ' ' + HOSTNAME : "") + " at port " + PORT + ".");
app.listen({ hostname: HOSTNAME, port: PORT });

import type { Metadata } from "next";
import { P0Console } from "./P0Console";

export const metadata: Metadata = {
  title: "首盾视觉自动化｜P0 联调原型",
  description: "产品、画布、任务中心与 AI 协作契约的最小闭环。",
};

export default function Home() {
  return <P0Console />;
}

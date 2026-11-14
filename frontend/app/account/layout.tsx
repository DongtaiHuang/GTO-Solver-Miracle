import {redirect} from "next/navigation";

export default function AccountLayout({children}:{children:React.ReactNode}){
  if(process.env.NEXT_PUBLIC_GUEST_DEMO==="true") redirect("/");
  return children;
}

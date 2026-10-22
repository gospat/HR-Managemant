import { notFound } from "next/navigation";
import StaffProfile from "./staff-profile";

export default async function StaffPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  if (!/^[1-9]\d*$/.test(id)) notFound();
  return <StaffProfile id={id} />;
}

export default function Placeholder({ title }: { title: string }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-white p-16 text-center">
      <h2 className="text-lg font-semibold text-slate-700">{title}</h2>
      <p className="mt-2 text-sm text-slate-500">This screen arrives in a later phase of the frontend build.</p>
    </div>
  )
}

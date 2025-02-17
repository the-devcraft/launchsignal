import { CircleDollarSign } from "lucide-react";
import type { Invoice } from "../lib/types";
import { money } from "../lib/format";
export function BillingPanel({ invoices }: { invoices: Invoice[] }) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Workspace invoices</h2>
          <p>Amounts are reported in provider-supplied minor units.</p>
        </div>
        <span className="pill">Stripe fixture / webhook feed</span>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Invoice</th>
              <th>Status</th>
              <th>Amount due</th>
              <th>Amount paid</th>
              <th>Difference</th>
            </tr>
          </thead>
          <tbody>
            {invoices.map((x) => (
              <tr key={x.provider_id}>
                <td>
                  <strong>{x.provider_id}</strong>
                </td>
                <td>
                  <span className={`status ${x.status}`}>{x.status}</span>
                </td>
                <td>{money(x.amount_due, x.currency)}</td>
                <td>{money(x.amount_paid, x.currency)}</td>
                <td>{money(x.amount_paid - x.amount_due, x.currency)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!invoices.length && (
          <div className="empty compact">
            <CircleDollarSign size={28} />
            <p>No invoices are available for this workspace.</p>
          </div>
        )}
      </div>
      <p className="panel-footnote">
        Demo records are synthetic. Live events require a configured signing
        secret and an operator-managed customer mapping. This application does
        not initiate charges.
      </p>
    </section>
  );
}

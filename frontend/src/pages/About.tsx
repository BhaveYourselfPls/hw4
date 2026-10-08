import { Link } from 'react-router-dom'

export default function About() {
  return (
    <div className="page">
      <div className="shell">
        <div className="page-head">
          <span className="eyebrow">About Us</span>
          <h1 style={{ marginTop: 12 }}>Think tradition.</h1>
        </div>

        <div className="prose">
          <p>
            Campus Customs began in 1975, when a father opened a small Yale memorabilia shop across
            the street from campus. Fifty years later the store is still on the same corner, still
            family run — his sons took it over, and the handshake standards he set are the ones we
            still work by.
          </p>

          <div className="facts">
            <div className="fact">
              <strong>1975</strong>
              <span>Year the first store opened on Broadway</span>
            </div>
            <div className="fact">
              <strong>50 yrs</strong>
              <span>Serving students, parents and alumni</span>
            </div>
            <div className="fact">
              <strong>One roof</strong>
              <span>Retail and production, side by side</span>
            </div>
          </div>

          <h2>What we make</h2>
          <p>
            Officially licensed Yale apparel: short-sleeve tees, crewneck sweatshirts, pullover and
            full-zip hoodies, quarter-zips, performance long sleeves and fleece jackets. The
            catalogue runs from residential colleges and graduate schools to varsity sports and the
            family lineup — Yale Mom, Dad, Grandma, Grandpa, Aunt, Uncle. If someone in your life
            went here, there is a sweatshirt for it.
          </p>

          <h2>Made next door</h2>
          <p>
            Our screen printing and embroidery happen in a production facility beside the original
            store. Keeping it in-house is not nostalgia — it is how we hold quality steady and turn
            orders around quickly, whether it is one crewneck or a run for an entire team.
          </p>

          <h2>Beyond the storefront</h2>
          <p>
            What started as one retail shop now also handles large-scale printing and embroidery,
            graphic design, online fulfillment and complete event merchandise. Much of that work
            comes from relationships we have kept for decades, which is the part we are proudest of.
          </p>

          <h2>Come visit</h2>
          <p>
            Find us at 57 Broadway in New Haven, a short walk from Old Campus. Come see the weights
            and fits in person, or browse the full collection online and let our merch assistant
            help you narrow it down.
          </p>

          <Link className="btn btn-dark" to="/products" style={{ marginTop: 12 }}>
            Browse the collection
          </Link>
        </div>
      </div>
    </div>
  )
}

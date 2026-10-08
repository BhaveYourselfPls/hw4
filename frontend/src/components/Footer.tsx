import { Link } from 'react-router-dom'

export default function Footer() {
  return (
    <footer className="footer">
      <div className="shell">
        <div className="footer-cols">
          <div>
            <h4>Campus Customs</h4>
            <p>
              Yale apparel and gifts, printed and embroidered a short walk from Old Campus.
              Family run since 1975.
            </p>
            <p>57 Broadway, New Haven, CT 06511</p>
          </div>

          <div>
            <h4>Shop</h4>
            <ul>
              <li><Link to="/products?category=T-Shirts">T-Shirts</Link></li>
              <li><Link to="/products?category=Crewnecks">Crewnecks</Link></li>
              <li><Link to="/products?category=Hoodies">Hoodies</Link></li>
              <li><Link to="/products?category=Jackets">Jackets</Link></li>
            </ul>
          </div>

          <div>
            <h4>Store</h4>
            <ul>
              <li><Link to="/about">About Us</Link></li>
              <li><Link to="/products">All Products</Link></li>
              <li><Link to="/login">Log In</Link></li>
              <li><Link to="/create-account">Create Account</Link></li>
            </ul>
          </div>
        </div>

        <div className="footer-base">
          <span>© {new Date().getFullYear()} Campus Customs. All rights reserved.</span>
          <span>Think tradition.</span>
        </div>
      </div>
    </footer>
  )
}

import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'

const links = [
  { to: '/', label: 'Home', end: true },
  { to: '/products', label: 'Products' },
  { to: '/about', label: 'About Us' },
]

export default function NavBar() {
  const { user, loading, logout } = useAuth()
  const navigate = useNavigate()

  return (
    <header className="nav">
      <div className="nav-banner">Officially Licensed Yale Merchandise · New Haven, CT</div>
      <div className="shell nav-inner">
        <NavLink to="/" className="brand">
          <span className="brand-mark">Campus Customs</span>
          <span className="brand-sub">Est. 1975</span>
        </NavLink>

        <nav className="nav-links">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
            >
              {link.label}
            </NavLink>
          ))}

          <span className="nav-divider" />

          {loading ? null : user ? (
            <>
              <span className="nav-user">
                Hi, {user.first_name || user.name.split(' ')[0]}
              </span>
              <button
                className="nav-link nav-button"
                onClick={() => {
                  logout()
                  navigate('/')
                }}
              >
                Log Out
              </button>
            </>
          ) : (
            <>
              <NavLink
                to="/login"
                className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
              >
                Log In
              </NavLink>
              <NavLink to="/create-account" className="nav-cta">
                Create Account
              </NavLink>
            </>
          )}
        </nav>
      </div>
    </header>
  )
}

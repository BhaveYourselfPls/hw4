import { Route, Routes } from 'react-router-dom'
import NavBar from './components/NavBar'
import Footer from './components/Footer'
import SizeBar from './components/SizeBar'
import ChatWidget from './components/ChatWidget'
import Home from './pages/Home'
import Products from './pages/Products'
import ProductDetail from './pages/ProductDetail'
import About from './pages/About'
import LogIn from './pages/LogIn'
import CreateAccount from './pages/CreateAccount'

export default function App() {
  return (
    <>
      <NavBar />
      <SizeBar />
      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/products" element={<Products />} />
          <Route path="/products/:productId" element={<ProductDetail />} />
          <Route path="/about" element={<About />} />
          <Route path="/login" element={<LogIn />} />
          <Route path="/create-account" element={<CreateAccount />} />
          <Route
            path="*"
            element={
              <div className="page">
                <div className="shell state">
                  <h3>Page not found</h3>
                  <p>That link does not lead anywhere.</p>
                </div>
              </div>
            }
          />
        </Routes>
      </main>
      <Footer />
      <ChatWidget />
    </>
  )
}

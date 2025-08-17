import { AuthProvider } from './context/AuthContext';
import './App.css';
import OnePageApp from './components/OnePageApp';

function App() {
  return (
    <AuthProvider>
      <OnePageApp />
    </AuthProvider>
  );
}

export default App;
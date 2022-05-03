import * as React from 'react';
import { Routes, Route, Navigate, Link } from 'react-router-dom';

import { styled, Theme, CSSObject } from '@mui/material/styles';
import Box from '@mui/material/Box';
import MuiDrawer from '@mui/material/Drawer';
import MuiAppBar, { AppBarProps as MuiAppBarProps } from '@mui/material/AppBar';
import Toolbar from '@mui/material/Toolbar';
import List from '@mui/material/List';
import CssBaseline from '@mui/material/CssBaseline';
import Typography from '@mui/material/Typography';
import Divider from '@mui/material/Divider';
import IconButton from '@mui/material/IconButton';
import MenuIcon from '@mui/icons-material/Menu';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ListItem from '@mui/material/ListItem';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';

import CurrencyExchangeIcon from '@mui/icons-material/CurrencyExchange';
import AnalyticsOutlinedIcon from '@mui/icons-material/AnalyticsOutlined';
import TimelineIcon from '@mui/icons-material/Timeline';
import SettingsOutlinedIcon from '@mui/icons-material/SettingsOutlined';
import AccountBalanceOutlinedIcon from '@mui/icons-material/AccountBalanceOutlined';
import SearchIcon from '@mui/icons-material/Search';
import NotificationsNoneIcon from '@mui/icons-material/NotificationsNone';
import { Refresh, Speed } from '@mui/icons-material';
import { CircularProgress, Icon, LinearProgress } from '@mui/material';

import { Config } from './common';
import { Trades } from './sections/Trades';
import { Overview } from './sections/Overview';
import { Performance } from './sections/Performance';
import { Charts } from './sections/Charts';
import { Settings } from './sections/Settings';
import { Values } from './sections/Values';
import { Prices } from './sections/Prices';
import { Dividends } from './sections/Dividends';

const drawerWidth = 240;

const openedMixin = (theme: Theme): CSSObject => ({
  width: drawerWidth,
  transition: theme.transitions.create('width', {
    easing: theme.transitions.easing.sharp,
    duration: theme.transitions.duration.enteringScreen,
  }),
  overflowX: 'hidden',
});

const closedMixin = (theme: Theme): CSSObject => ({
  transition: theme.transitions.create('width', {
    easing: theme.transitions.easing.sharp,
    duration: theme.transitions.duration.leavingScreen,
  }),
  overflowX: 'hidden',
  width: `calc(${theme.spacing(7)} + 1px)`,
  [theme.breakpoints.up('sm')]: {
    width: `calc(${theme.spacing(9)} + 1px)`,
  },
});

const DrawerHeader = styled('div')(({ theme }) => ({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'flex-end',
  padding: theme.spacing(0, 1),
  // necessary for content to be below app bar
  ...theme.mixins.toolbar,
}));

interface AppBarProps extends MuiAppBarProps {
  open?: boolean;
}

const AppBar = styled(MuiAppBar, {
  shouldForwardProp: (prop) => prop !== 'open',
})<AppBarProps>(({ theme, open }) => ({
  zIndex: theme.zIndex.drawer + 1,
  transition: theme.transitions.create(['width', 'margin'], {
    easing: theme.transitions.easing.sharp,
    duration: theme.transitions.duration.leavingScreen,
  }),
  ...(open && {
    marginLeft: drawerWidth,
    width: `calc(100% - ${drawerWidth}px)`,
    transition: theme.transitions.create(['width', 'margin'], {
      easing: theme.transitions.easing.sharp,
      duration: theme.transitions.duration.enteringScreen,
    }),
  }),
}));

const Drawer = styled(MuiDrawer, { shouldForwardProp: (prop) => prop !== 'open' })(
  ({ theme, open }) => ({
    width: drawerWidth,
    flexShrink: 0,
    whiteSpace: 'nowrap',
    boxSizing: 'border-box',
    ...(open && {
      ...openedMixin(theme),
      '& .MuiDrawer-paper': openedMixin(theme),
    }),
    ...(!open && {
      ...closedMixin(theme),
      '& .MuiDrawer-paper': closedMixin(theme),
    }),
  }),
);

interface LastData {
  historical: string;
  fx: string;
  manual_value: string;
}

interface AppState {
  refreshing: boolean;
  isBusy: boolean;
  menuOpen: boolean;
  lastData: LastData;
  heading: string;
  config: Config;
}

export default class App extends React.Component<{}, AppState> {

  constructor(props:{}) {
    super(props);
    this.state = {
      config: {
        base_currency: '',
        language_locale: '',
      },
      refreshing: false,
      isBusy: false,
      menuOpen: false,
      lastData: {
        historical: '',
        fx: '',
        manual_value: '',
      },
      heading: '',
    }

    this.displayProgressBar = this.displayProgressBar.bind(this);
    this.setHeading = this.setHeading.bind(this);
  }

  componentDidMount() {
    this.loadConfig();
    this.loadLastDataDates();
  }

  loadConfig = () => {
    return fetch('/config/get')
      .then<Config>(res => res.json())
      .then(config => this.setState({config}));
  }

  loadLastDataDates = () => {
    return fetch('/data/last')
      .then(res => res.json())
      .then(lastData => this.setState({lastData, refreshing: false}));
  }

  refreshData = () => {
    this.setState({refreshing: true});
    return fetch('/historical/update').then(res =>
      fetch('/fx/update').then(res =>
        this.loadLastDataDates()
      )
    )
  }

  displayProgressBar(isBusy: boolean) {
    this.setState({isBusy});
  }

  setHeading(heading: string) {
    this.setState({heading});
  }

  render() {
    return (
      <Box sx={{ display: 'flex' }}>
        <CssBaseline />
        <AppBar position="fixed" open={this.state.menuOpen}>
          <Toolbar>
            <IconButton
              color="inherit"
              aria-label="open drawer"
              onClick={() => this.setState({menuOpen: true})}
              edge="start"
              sx={{
                marginRight: '36px',
                ...(this.state.menuOpen && { display: 'none' }),
              }}
            >
              <MenuIcon />
            </IconButton>
            <Typography variant="h6" noWrap component="div">{this.state.heading}</Typography>

            <Toolbar sx={{marginLeft: 'auto'}} >
              <Typography variant="body1" noWrap component="div" >
                {Object.entries(this.state.lastData).map(([k, v]) => `${k}: ${v}`).join(' | ')}
              </Typography>
              {this.state.refreshing ?
                <Icon sx={{marginLeft: '36px'}}>
                  <CircularProgress color="inherit" size="small"/>
                </Icon>:
                <IconButton
                  color="inherit"
                  onClick={this.refreshData}
                  edge="start"
                  sx={{marginLeft: '36px'}}
                >
                  <Refresh />
                </IconButton>
              }
            </Toolbar>
          </Toolbar>
          {this.state.isBusy ? <LinearProgress /> : null}
        </AppBar>
        <Drawer variant="permanent" open={this.state.menuOpen}>
          <DrawerHeader>
            <IconButton onClick={() => this.setState({menuOpen: false})}><ChevronLeftIcon /></IconButton>
          </DrawerHeader>
          <Divider />
          <List>
            <Link to="/overview" style={{color: 'inherit', textDecoration: 'none'}}>
              <ListItem button key="overview">
                <ListItemIcon><AnalyticsOutlinedIcon /></ListItemIcon>
                <ListItemText primary="Overview" />
              </ListItem>
            </Link>
            <Link to="/performance" style={{color: 'inherit', textDecoration: 'none'}}>
              <ListItem button key="performance">
                <ListItemIcon><Speed /></ListItemIcon>
                <ListItemText primary="Performance" />
              </ListItem>
            </Link>
            <Link to="/charts" style={{color: 'inherit', textDecoration: 'none'}}>
              <ListItem button key="charts">
                <ListItemIcon><TimelineIcon /></ListItemIcon>
                <ListItemText primary="Charts" />
              </ListItem>
            </Link>
            <Link to="/trades" style={{color: 'inherit', textDecoration: 'none'}}>
              <ListItem button key="trades">
                <ListItemIcon><CurrencyExchangeIcon /></ListItemIcon>
                <ListItemText primary="Trades" />
              </ListItem>
            </Link>
            <Link to="/dividends" style={{color: 'inherit', textDecoration: 'none'}}>
              <ListItem button key="dividends">
                <ListItemIcon><NotificationsNoneIcon /></ListItemIcon>
                <ListItemText primary="Dividends" />
              </ListItem>
            </Link>
            <Link to="/values" style={{color: 'inherit', textDecoration: 'none'}}>
              <ListItem button key="values">
                <ListItemIcon><AccountBalanceOutlinedIcon /></ListItemIcon>
                <ListItemText primary="Values" />
              </ListItem>
            </Link>
            <Link to="/prices" style={{color: 'inherit', textDecoration: 'none'}}>
              <ListItem button key="prices">
                <ListItemIcon><SearchIcon /></ListItemIcon>
                <ListItemText primary="Prices" />
              </ListItem>
            </Link>
            <Link to="/settings" style={{color: 'inherit', textDecoration: 'none'}}>
              <ListItem button key="settings">
                <ListItemIcon><SettingsOutlinedIcon /></ListItemIcon>
                <ListItemText primary="Settings" />
              </ListItem>
            </Link>
          </List>
        </Drawer>
        <Box component="main" sx={{ flexGrow: 1, p: 3 }}>
          <DrawerHeader />
          <Routes>
            <Route path="/overview" element={
              <Overview config={this.state.config} setHeading={this.setHeading} displayProgressBar={this.displayProgressBar} />
            }/>
            <Route path="/performance" element={
              <Performance config={this.state.config} setHeading={this.setHeading} displayProgressBar={this.displayProgressBar} />
            }/>
            <Route path="/trades" element={
              <Trades config={this.state.config} setHeading={this.setHeading} displayProgressBar={this.displayProgressBar} />
            }/>
            <Route path="/dividends" element={
              <Dividends config={this.state.config} setHeading={this.setHeading} displayProgressBar={this.displayProgressBar} />
            }/>
            <Route path="/charts" element={
              <Charts config={this.state.config} setHeading={this.setHeading} displayProgressBar={this.displayProgressBar} />
            }/>
            <Route path="/settings" element={
              <Settings config={this.state.config} setHeading={this.setHeading} displayProgressBar={this.displayProgressBar} />
            }/>
            <Route path="/values" element={
              <Values config={this.state.config} setHeading={this.setHeading} displayProgressBar={this.displayProgressBar} />
            }/>
            <Route path="/prices" element={
              <Prices config={this.state.config} setHeading={this.setHeading} displayProgressBar={this.displayProgressBar} />
            }/>
            <Route path="/" element={<Navigate to="/overview" />} />
          </Routes>
        </Box>
      </Box>
    );
  }
}

import * as React from 'react';
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

import { Trades } from './sections/Trades';
import { Overview } from './sections/Overview';
import { Charts } from './sections/Charts';
import { Settings } from './sections/Settings';
import { Values } from './sections/Values';
import { Refresh } from '@mui/icons-material';
import { CircularProgress, Icon } from '@mui/material';

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
  isBusy: boolean;
  menuOpen: boolean;
  section: 'overview'|'charts'|'trades'|'values'|'settings';
  lastData: LastData;
}

export default class App extends React.Component<{}, AppState> {

  constructor() {
    super({});
    this.state = {
      isBusy: false,
      menuOpen: false,
      section: 'overview',
      lastData: {
        historical: '',
        fx: '',
        manual_value: '',
      }
    }

    this.loadLastDataDates = this.loadLastDataDates.bind(this);
    this.refreshData = this.refreshData.bind(this);
  }

  componentDidMount() {
    this.loadLastDataDates();
  }

  loadLastDataDates = () => {
      return fetch('/data/last')
        .then(res => res.json())
        .then(lastData => this.setState({lastData, isBusy: false}));
  }

  refreshData = () => {
    this.setState({isBusy: true});
    return fetch('/historical/update').then(res =>
      fetch('/fx/update').then(res =>
        this.loadLastDataDates()
      )
    )
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
            <Typography variant="h6" noWrap component="div">
              {this.state.section[0].toUpperCase() + this.state.section.slice(1)}
            </Typography>

            <Toolbar sx={{marginLeft: 'auto'}} >
              <Typography variant="body1" noWrap component="div" >
                {Object.entries(this.state.lastData).map(([k, v]) => `${k}: ${v}`).join(' | ')}
              </Typography>
              {this.state.isBusy ?
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
        </AppBar>
        <Drawer variant="permanent" open={this.state.menuOpen}>
          <DrawerHeader>
            <IconButton onClick={() => this.setState({menuOpen: false})}><ChevronLeftIcon /></IconButton>
          </DrawerHeader>
          <Divider />
          <List>
            <ListItem button key="overview" onClick={() => this.setState({section: 'overview'})}>
              <ListItemIcon><AnalyticsOutlinedIcon /></ListItemIcon>
              <ListItemText primary="Overview" />
            </ListItem>
            <ListItem button key="charts" onClick={() => this.setState({section: 'charts'})}>
              <ListItemIcon><TimelineIcon /></ListItemIcon>
              <ListItemText primary="Charts" />
            </ListItem>
            <ListItem button key="trades" onClick={() => this.setState({section: 'trades'})}>
              <ListItemIcon><CurrencyExchangeIcon /></ListItemIcon>
              <ListItemText primary="Trades" />
            </ListItem>
            <ListItem button key="values" onClick={() => this.setState({section: 'values'})}>
              <ListItemIcon><AccountBalanceOutlinedIcon /></ListItemIcon>
              <ListItemText primary="Values" />
            </ListItem>
            <ListItem button key="settings" onClick={() => this.setState({section: 'settings'})}>
              <ListItemIcon><SettingsOutlinedIcon /></ListItemIcon>
              <ListItemText primary="Settings" />
            </ListItem>
          </List>
        </Drawer>
        <Box component="main" sx={{ flexGrow: 1, p: 3 }}>
          <DrawerHeader />
          {this.state.section === 'overview' ? <Overview /> : null}
          {this.state.section === 'trades' ? <Trades /> : null}
          {this.state.section === 'charts' ? <Charts /> : null}
          {this.state.section === 'settings' ? <Settings /> : null}
          {this.state.section === 'values' ? <Values /> : null}
        </Box>
      </Box>
    );
  }
}

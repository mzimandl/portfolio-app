import * as React from 'react';
import { Table, TableBody, TableHead, TableContainer, TableRow, TableCell, Box, IconButton, FormControl, Select, InputLabel, MenuItem } from '@mui/material';
import CircularProgress from '@mui/material/CircularProgress';
import TextField from '@mui/material/TextField';
import { AddBox } from '@mui/icons-material';
import { InstrumentDataRow } from './Settings';


interface DataRow {
    date: string;
    ticker: string;
    volume: number;
    price: number;
    fee: number;
    rate: number;
}

interface NewDataRow {
    date: string;
    ticker: string;
    volume: string;
    price: string;
    fee: string;
    rate: string;
}

export class Trades extends React.Component<{}, {busy: boolean; trades: Array<DataRow>; newTrade: NewDataRow; instruments: Array<InstrumentDataRow>}> {

    constructor(props:{}) {
        super(props);
        this.state = {
            busy: true,
            trades: [],
            instruments: [],
            newTrade: {
                date: '',
                ticker: '',
                volume: '',
                price: '',
                fee: '',
                rate: '',
            }
        };

        this.loadInstruments = this.loadInstruments.bind(this);
        this.loadTrades = this.loadTrades.bind(this);

        this.addTrade = this.addTrade.bind(this);
    }

    componentDidMount() {
        this.loadInstruments().then(() =>
            this.loadTrades().then(() =>
                this.setState({busy: false})
            )
        );
    }

    loadInstruments = () => {
        return fetch('/instruments/list')
            .then(res => res.json())
            .then(instruments => this.setState({instruments}));
    }

    loadTrades = () => {
        const params = new URLSearchParams();
        // params.append('ticker', 'CEZ.PR');
        return fetch(`/trades/list?${params.toString()}`)
            .then(res => res.json())
            .then(trades => this.setState({trades}));
    }

    addTrade = () => {
        if (this.state.newTrade.ticker && this.state.newTrade.date) {
            this.setState({busy: true});
            fetch('/trades/new', {method: 'POST', body: JSON.stringify(this.state.newTrade)})
                .then(res => {
                    this.setState({
                        newTrade: {
                            date: '',
                            ticker: '',
                            volume: '',
                            price: '',
                            fee: '',
                            rate: '',
                        }
                    });
                    this.loadTrades().then(() => this.setState({busy: false}));
                });
        }
    }

    render() {

        return <Box>
            {this.state.busy ?
                <CircularProgress /> :
                <TableContainer>
                    <Table size="small">
                        <TableHead>
                            <TableRow>
                                <TableCell>
                                    <TextField label="Date" variant="outlined" size='small' margin='none' fullWidth
                                    onChange={(e) => this.setState({newTrade: {...this.state.newTrade, date: e.target.value}})} />
                                </TableCell>
                                <TableCell>
                                    <FormControl fullWidth size='small'>
                                        <InputLabel id="ticker-select-label">Ticker</InputLabel>
                                        <Select
                                            labelId='ticker-select-label'
                                            value={this.state.newTrade.ticker}
                                            label="Ticker"
                                            onChange={(e) => this.setState({newTrade: {...this.state.newTrade, ticker: e.target.value}})}
                                        >
                                            {this.state.instruments.map(v => <MenuItem key={v.ticker} value={v.ticker}>{v.ticker}</MenuItem>)}
                                        </Select>
                                    </FormControl>
                                </TableCell>
                                <TableCell>
                                    <TextField label="Volume" variant="outlined" size='small' margin='none' fullWidth
                                    onChange={(e) => this.setState({newTrade: {...this.state.newTrade, volume: e.target.value}})} />
                                </TableCell>
                                <TableCell>
                                    <TextField label="Price" variant="outlined" size='small' margin='none' fullWidth
                                    onChange={(e) => this.setState({newTrade: {...this.state.newTrade, price: e.target.value}})} />
                                </TableCell>
                                <TableCell>
                                    <TextField label="Exchange rate" variant="outlined" size='small' margin='none' fullWidth
                                    onChange={(e) => this.setState({newTrade: {...this.state.newTrade, rate: e.target.value}})} />
                                </TableCell>
                                <TableCell>
                                    <TextField label="Fee" variant="outlined" size='small' margin='none' fullWidth
                                    onChange={(e) => this.setState({newTrade: {...this.state.newTrade, fee: e.target.value}})} />
                                </TableCell>
                                <TableCell><IconButton onClick={this.addTrade}><AddBox/></IconButton></TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {this.state.trades.map(
                                (item, i) => <TableRow key={i}>
                                    <TableCell>{item.date}</TableCell>
                                    <TableCell>{item.ticker}</TableCell>
                                    <TableCell>{item.volume}</TableCell>
                                    <TableCell>{item.price}</TableCell>
                                    <TableCell>{item.rate}</TableCell>
                                    <TableCell>{item.fee}</TableCell>
                                    <TableCell></TableCell>
                                </TableRow>
                            )}
                        </TableBody>
                    </Table>
                </TableContainer>}
        </Box>
    }
}
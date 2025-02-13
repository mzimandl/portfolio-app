import React from "react";
import { AbstractSection, numberIsValid, SectionProps } from '../../common';
import { Table, TableBody, TableHead, TableContainer, TableRow, TableCell, Box, IconButton, FormControl, Select, InputLabel, MenuItem } from '@mui/material';
import TextField from '@mui/material/TextField';
import { AddBox } from '@mui/icons-material';
import { InstrumentDataRow, InstrumentsResponse } from '../Settings';


interface DataRow {
    date: string;
    ticker: string;
    volume: number;
    price: number;
    fee: number;
    rate: number;
    currency: string;
}

interface NewDataRow {
    date: string;
    ticker: string;
    volume: string;
    price: string;
    fee: string;
    rate: string;
}

type TradesResponse = Array<DataRow>;

interface TradesState {
    trades: Array<DataRow>;
    instruments: Array<InstrumentDataRow>;
}

interface TradesProps {}
interface NewTradeTableRowProps {
    instruments:Array<InstrumentDataRow>;
    addTrade:(newTrade:NewDataRow) => void;
}

class NewTradeTableRow extends React.Component<NewTradeTableRowProps, NewDataRow> {

    constructor(props:NewTradeTableRowProps) {
        super(props);
        this.state = {
            date: '',
            ticker: '',
            volume: '0',
            price: '0',
            fee: '0',
            rate: '1',
        }
    }

    render() {
        return <TableRow>
            <TableCell>
                <TextField label="Date" variant="outlined" size='small' margin='none' fullWidth
                onChange={(e) => this.setState({date: e.target.value})} />
            </TableCell>
            <TableCell>
                <FormControl fullWidth size='small'>
                    <InputLabel id="ticker-select-label">Ticker</InputLabel>
                    <Select
                        labelId='ticker-select-label'
                        value={this.state.ticker}
                        label="Ticker"
                        onChange={(e) => this.setState({ticker: e.target.value})}
                    >
                        {this.props.instruments
                            .filter(v => v.evaluation !== 'manual')
                            .map(v => <MenuItem key={v.ticker} value={v.ticker}>{v.ticker}</MenuItem>)
                        }
                    </Select>
                </FormControl>
            </TableCell>
            <TableCell>
                <TextField value={this.state.volume} label="Volume" variant="outlined" size='small' margin='none' fullWidth
                onChange={(e) => numberIsValid(e.target.value) ? this.setState({volume: e.target.value}) : null} />
            </TableCell>
            <TableCell>
                <TextField value={this.state.price} label="Price" variant="outlined" size='small' margin='none' fullWidth
                onChange={(e) => numberIsValid(e.target.value) ? this.setState({price: e.target.value}) : null} />
            </TableCell>
            <TableCell>
                <TextField value={this.state.rate} label="Exchange rate" variant="outlined" size='small' margin='none' fullWidth
                onChange={(e) => numberIsValid(e.target.value) ? this.setState({rate: e.target.value}) : null} />
            </TableCell>
            <TableCell>
                <TextField value={this.state.fee} label="Fee" variant="outlined" size='small' margin='none' fullWidth
                onChange={(e) => numberIsValid(e.target.value) ? this.setState({fee: e.target.value}) : null} />
            </TableCell>
            <TableCell><IconButton onClick={e => this.props.addTrade(this.state)}><AddBox/></IconButton></TableCell>
        </TableRow>
    }
}

export class Trades extends AbstractSection<TradesProps, TradesState> {

    sectionName = () => 'Trades';

    constructor(props:TradesProps & SectionProps) {
        super(props);
        this.state = {
            trades: [],
            instruments: [],
        };

        this.addTrade = this.addTrade.bind(this);
    }

    componentDidMount() {
        super.componentDidMount();
        this.props.displayProgressBar(true);
        this.loadInstruments().then(() =>
            this.loadTrades().then(() =>
                this.props.displayProgressBar(false)
            )
        );
    }

    loadInstruments = () => {
        return fetch('/instruments/list')
            .then<InstrumentsResponse>(res => res.json())
            .then(instruments => this.setState({instruments}));
    }

    loadTrades = () => {
        const params = new URLSearchParams();
        // params.append('ticker', 'CEZ.PR');
        return fetch(`/trades/list?${params.toString()}`)
            .then<TradesResponse>(res => res.json())
            .then(trades => this.setState({trades}));
    }

    addTrade = (newTrade:NewDataRow) => {
        if (newTrade.ticker && newTrade.date) {
            this.props.displayProgressBar(true);
            fetch('/trades/new', {method: 'POST', body: JSON.stringify(newTrade)})
                .then(res => {
                    this.loadTrades().then(() => {
                        this.props.displayProgressBar(false);
                    });
                });
        }
    }

    render() {

        return <Box>
            <TableContainer>
                <Table size="small">
                    <TableHead>
                        <NewTradeTableRow instruments={this.state.instruments} addTrade={this.addTrade} />
                    </TableHead>
                    <TableBody>
                        {this.state.trades.map(
                            (item, i) => <TableRow key={i}>
                                <TableCell>{item.date}</TableCell>
                                <TableCell>{item.ticker}</TableCell>
                                <TableCell>{item.volume}</TableCell>
                                <TableCell>{this.formatCurrency(item.price, {currency: item.currency})}</TableCell>
                                <TableCell>{this.formatCurrency(item.rate, {currency: item.currency})}</TableCell>
                                <TableCell colSpan={2}>{this.formatCurrency(item.fee)}</TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
            </TableContainer>
        </Box>
    }
}
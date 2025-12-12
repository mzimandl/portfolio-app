import React from "react";
import { AbstractSection, numberIsValid, SectionProps } from '../../common';
import { Table, TableBody, TableHead, TableContainer, TableRow, TableCell, Box, IconButton, FormControl, Select, InputLabel, MenuItem, Checkbox } from '@mui/material';
import TextField from '@mui/material/TextField';
import RecyclingIcon from '@mui/icons-material/Recycling';
import { AddBox, Check } from '@mui/icons-material';
import { InstrumentDataRow, InstrumentsResponse } from '../Settings';


interface DataRow {
    date: string;
    ticker: string;
    volume: number;
    price: number;
    fee: number;
    baseRate: number;
    currency: string;
    reinvested: number;
}

interface NewDataRow {
    date: string;
    ticker: string;
    volume: string;
    volumeValid: boolean;
    price: string;
    priceValid: boolean;
    fee: string;
    feeValid: boolean;
    currency: string;
    baseRate: string;
    baseRateValid: boolean;
    reinvested: number;
}

type CurrenciesResponse = Array<string>;
type CryptoResponse = Array<DataRow>;

interface CryptoState {
    crypto: Array<DataRow>;
    instruments: Array<InstrumentDataRow>;
    currencies: CurrenciesResponse;
}

interface CryptoProps {}
interface NewCryptoTableRowProps {
    instruments:Array<InstrumentDataRow>;
    currencies: CurrenciesResponse;
    addCrypto:(newCrypto:NewDataRow) => void;
}

class NewCryptoTableRow extends React.Component<NewCryptoTableRowProps, NewDataRow> {

    constructor(props:NewCryptoTableRowProps) {
        super(props);
        this.state = {
            date: '',
            ticker: '',
            volume: '0',
            volumeValid: true,
            price: '0',
            priceValid: true,
            fee: '0',
            feeValid: true,
            currency: '',
            baseRate: '1',
            baseRateValid: true,
            reinvested: 0,
        }
    }

    validate() {
        return !!this.state.date && !!this.state.ticker && this.state.volumeValid && this.state.priceValid && this.state.feeValid && !!this.state.currency && this.state.baseRateValid;
    }

    render() {
        return <TableRow>
            <TableCell>
                <TextField label="Date" variant="outlined" size='small' margin='none' fullWidth
                onChange={(e) => this.setState({date: e.target.value})}
                error={!this.state.date} />
            </TableCell>
            <TableCell>
                <FormControl fullWidth size='small'>
                    <InputLabel id="ticker-select-label">Ticker</InputLabel>
                    <Select
                        labelId='ticker-select-label'
                        value={this.state.ticker}
                        label="Ticker"
                        onChange={(e) => this.setState({ticker: e.target.value})}
                        error={!this.state.ticker}
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
                onChange={(e) => this.setState({volume: e.target.value, volumeValid: numberIsValid(e.target.value)})}
                error={!this.state.volumeValid} />
            </TableCell>
            <TableCell>
                <TextField value={this.state.price} label="Price" variant="outlined" size='small' margin='none' fullWidth
                onChange={(e) => this.setState({price: e.target.value, priceValid: numberIsValid(e.target.value)})}
                error={!this.state.priceValid} />
            </TableCell>
            <TableCell>
            <FormControl fullWidth size='small'>
                    <InputLabel id="currency-select-label">Currency</InputLabel>
                    <Select
                        labelId='currency-select-label'
                        value={this.state.currency}
                        label="Currency"
                        onChange={(e) => this.setState({currency: e.target.value})}
                        error={!this.state.currency}
                    >
                        {this.props.currencies.map(v => <MenuItem key={v} value={v}>{v}</MenuItem>)}
                    </Select>
                </FormControl>
            </TableCell>
            <TableCell>
                <TextField value={this.state.baseRate} label="Base rate" variant="outlined" size='small' margin='none' fullWidth
                onChange={(e) => this.setState({baseRate: e.target.value, baseRateValid: numberIsValid(e.target.value)})}
                error={!this.state.baseRateValid} />
            </TableCell>
            <TableCell>
                <TextField value={this.state.fee} label="Fee" variant="outlined" size='small' margin='none' fullWidth
                onChange={(e) => this.setState({fee: e.target.value, feeValid: numberIsValid(e.target.value)})}
                error={!this.state.feeValid} />
            </TableCell>
            <TableCell>
                <RecyclingIcon style={{verticalAlign: 'middle'}}/>
                <Checkbox checked={this.state.reinvested === 1} size='small'
                onChange={(e) => this.setState({reinvested: e.target.checked ? 1 : 0})} />
            </TableCell>
            <TableCell><IconButton disabled={!this.validate()} onClick={e => this.props.addCrypto(this.state)}><AddBox/></IconButton></TableCell>
        </TableRow>
    }
}

export class Crypto extends AbstractSection<CryptoProps, CryptoState> {

    sectionName = () => 'Crypto';

    constructor(props:CryptoProps & SectionProps) {
        super(props);
        this.state = {
            crypto: [],
            instruments: [],
            currencies: [],
        };

        this.addCrypto = this.addCrypto.bind(this);
    }

    componentDidMount() {
        super.componentDidMount();
        this.props.displayProgressBar(true);
        this.loadCurrencies().then(() =>
            this.loadInstruments().then(() =>
                this.loadCrypto().then(() =>
                    this.props.displayProgressBar(false)
                )
            )
        );
    }

    loadCurrencies = () => {
        return fetch('/currencies/list')
            .then<CurrenciesResponse>(res => res.json())
            .then(currencies => this.setState({currencies}));
    }

    loadInstruments = () => {
        return fetch('/instruments/list?active=1')
            .then<InstrumentsResponse>(res => res.json())
            .then(instruments => this.setState({instruments}));
    }

    loadCrypto = () => {
        const params = new URLSearchParams();
        // params.append('ticker', 'CEZ.PR');
        return fetch(`/crypto/list?${params.toString()}`)
            .then<CryptoResponse>(res => res.json())
            .then(crypto => this.setState({crypto}));
    }

    addCrypto = (newCrypto:NewDataRow) => {
        this.props.displayProgressBar(true);
        fetch('/crypto/new', {method: 'POST', body: JSON.stringify(newCrypto)})
            .then(res => {
                this.loadCrypto().then(() => {
                    this.props.displayProgressBar(false);
                });
            });
    }

    render() {

        return <Box>
            <TableContainer>
                <Table size="small">
                    <TableHead>
                        <NewCryptoTableRow currencies={this.state.currencies} instruments={this.state.instruments} addCrypto={this.addCrypto} />
                    </TableHead>
                    <TableBody>
                        {this.state.crypto.map(
                            (item, i) => <TableRow key={i}>
                                <TableCell>{item.date}</TableCell>
                                <TableCell>{item.ticker}</TableCell>
                                <TableCell>{item.volume}</TableCell>
                                <TableCell colSpan={2}>{this.formatCurrency(item.price, {currency: item.currency})}</TableCell>
                                <TableCell>{this.formatCurrency(item.baseRate, {currency: item.currency})}</TableCell>
                                <TableCell>{this.formatCurrency(item.fee)}</TableCell>
                                <TableCell colSpan={2}>{item.reinvested === 1 ? <Check/> : null}</TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
            </TableContainer>
        </Box>
    }
}